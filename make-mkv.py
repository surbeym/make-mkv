import subprocess
import time
import os
import sys
import re
import threading
import ctypes
import requests
from tqdm import tqdm

# --- Windows Configuration ---
MAKEMKV_BIN = r"C:\Program Files (x86)\MakeMKV\makemkvcon.exe"
BASE_OUTPUT_DIR = r"D:\Video"

# --- Title Filters (ISO-8601 Format) ---
# Format: PT[H]H[M]M[S]S  (e.g., PT1H10M or PT15M)
MIN_LENGTH_ISO = "PT30M"
MAX_LENGTH_ISO = "PT1H"
INFO_TIMEOUT_ISO = "PT10M00S"

# --- Delay Configuration ---
# How long to wait for you to swap the disc before the script tries to scan again
SWAP_DELAY_ISO = "PT1M"  # 1 Minute (Change to PT2M, PT30S, etc.)

# --- Notification Configuration ---
# Home Assistant Webhook URL (set via environment variable or override with --url)
# Default: reads from HA_WEBHOOK_URL environment variable
HA_WEBHOOK_URL = os.getenv("HA_WEBHOOK_URL", "http://localhost:8123/api/webhook/rip_status_wh")

# Configured with a 2.5GB cache (--cache=2560) to maximize read speeds and reduce drive wear.
CACHE_SIZE=2560


# Add this to your Configuration section at the top
TARGET_DRIVE_NAME = ""

def iso_to_seconds(iso_str):
    """Converts PT format (e.g., PT1H10M30S) to total seconds."""
    pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
    match = re.match(pattern, iso_str)
    if not match:
        return 0

    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2)) if match.group(2) else 0
    seconds = int(match.group(3)) if match.group(3) else 0

    return (hours * 3600) + (minutes * 60) + seconds

# Convert ISO strings to integers
MIN_LENGTH = iso_to_seconds(MIN_LENGTH_ISO)
MAX_LENGTH = iso_to_seconds(MAX_LENGTH_ISO)
INFO_TIMEOUT = iso_to_seconds(INFO_TIMEOUT_ISO)
SWAP_DELAY = iso_to_seconds(SWAP_DELAY_ISO)


def get_drive_info():
    """Scans for a drive; returns (index, letter) or (None, None) if not found."""
    try:
        cmd = [MAKEMKV_BIN, "-r", "info", "dev:list"]
        # creationflags=0x08000000 is CREATE_NO_WINDOW
        result = subprocess.run(cmd, capture_output=True, text=True, creationflags=0x08000000)

        # Use an empty string check to avoid AnyStr warnings
        search_name = TARGET_DRIVE_NAME if TARGET_DRIVE_NAME else ""

        if search_name:
            # Look for specific name
            pattern = rf'DRV:(\d+),.*?"{re.escape(search_name)}.*?",".*?","([A-Z]:)"'
        else:
            # Look for any valid drive
            pattern = r'DRV:(\d+),.*?,.*?,.*?"([A-Z]:)"'

        match = re.search(pattern, result.stdout)

        if match:
            return match.group(1), match.group(2)

    except Exception as e:
        print(f"[!] Drive detection error: {e}")

    return None, None  # Return None to indicate failure

def windows_native_eject(letter):
    """Force eject via Windows IOCTL."""
    IOCTL_STORAGE_EJECT_MEDIA = 0x2D4808
    device_path = f"\\\\.\\{letter.strip(':')}:"
    handle = ctypes.windll.kernel32.CreateFileW(device_path, 0x80000000, 0x01 | 0x02, None, 3, 0, None)
    if handle != -1:
        ctypes.windll.kernel32.DeviceIoControl(handle, IOCTL_STORAGE_EJECT_MEDIA, None, 0, None, 0, ctypes.byref(ctypes.c_ulong()), None)
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    return False

def format_seconds_to_iso(seconds):
    h, m = seconds // 3600, (seconds % 3600) // 60
    parts = ["PT"]
    if h > 0: parts.append(f"{h}H")
    if m > 0: parts.append(f"{m}M")
    return "".join(parts) if len(parts) > 1 else "PT0S"

def get_raw_data_with_progress():
    """Queries the ASUS drive with an explicit minimum length filter."""
    raw_info = ""
    print(f"[{time.strftime('%H:%M:%S')}] Querying ASUS Drive (Index:{DRIVE_INDEX} / {DRIVE_LETTER})...")
    start_info = time.perf_counter() # Start Timer
    stop_timer = False

    def stopwatch():
        with tqdm(total=0, desc="Scanning Disc Info", bar_format='{l_bar}{bar}| {elapsed}', leave=False) as pbar:
            while not stop_timer:
                pbar.update(0)
                time.sleep(0.1)

    timer_thread = threading.Thread(target=stopwatch)
    timer_thread.start()

    try:
        # Changed 'dev:' to 'disc:' here
        cmd = [
            MAKEMKV_BIN, "-r", "info", f"disc:{DRIVE_INDEX}",
            f"--minlength={MIN_LENGTH}"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=INFO_TIMEOUT)
        raw_info = result.stdout
    except Exception as e:
        print(f"\n[!] Error during scan: {e}")
    finally:
        stop_timer = True
        timer_thread.join()

    end_info = time.perf_counter() # End Timer
    duration = end_info - start_info
    print(f"[*] Info scan completed in {duration:.2f} seconds.") # Log it
    return raw_info

def show_detailed_probe(raw_output):
    if not raw_output or "MSG:5073" in raw_output:
        print("\n[!] No titles found.")
        return 0
    name_match = re.search(r'CINFO:2,0,"(.+?)"', raw_output)
    disc_name = name_match.group(1) if name_match else "Unknown Volume"
    titles = re.findall(r'TINFO:(\d+),9,0,"(\d+:\d+:\d+)"', raw_output)
    print("\n" + "="*75 + f"\n PROBE REPORT for: {disc_name}\n" + "="*75)
    print(f"{'ID':<5} | {'Duration':<10} | {'Total Sec':<10} | {'Decision'}\n" + "-"*75)
    rip_count = 0
    for tid, dur in titles:
        h, m, s = map(int, dur.split(':'))
        total_sec = h*3600 + m*60 + s
        status = ">>> WILL RIP <<<" if MIN_LENGTH <= total_sec <= MAX_LENGTH else "SKIP"
        if status == ">>> WILL RIP <<<": rip_count += 1
        print(f"{tid:<5} | {dur:<10} | {total_sec:<10} | {status}")
    print("-" * 75)
    print(f"Summary: {rip_count} selected (Min: {MIN_LENGTH}s ({format_seconds_to_iso(MIN_LENGTH)}) / Max: {MAX_LENGTH}s ({format_seconds_to_iso(MAX_LENGTH)}))")
    return rip_count

def rip_disc(verify_mode=False, debug_mode=False):
    raw_info = get_raw_data_with_progress()
    if not raw_info or "MSG:5073" in raw_info or 'TINFO:' not in raw_info:
        print("\n[!] CRITICAL: No title information found.")
        return "STOP"

    # Parse all titles found
    titles = re.findall(r'TINFO:(\d+),9,0,"(\d+:\d+:\d+)"', raw_info)

    # Initial selection based on your PT filters
    selected_ids = [t[0] for t in titles if MIN_LENGTH <= (lambda x: int(x[0])*3600 + int(x[1])*60 + int(x[2]))(t[1].split(':')) <= MAX_LENGTH]

    show_detailed_probe(raw_info)
    if verify_mode:
        # show_detailed_probe(raw_info)
        print(f"\nCurrently selected based on filters: {', '.join(selected_ids) if selected_ids else 'None'}")
        print("-" * 30)
        print(" [Y] - Proceed with current selection")
        print(" [S] - Manually select IDs (e.g. 0,1,3)")
        print(" [E] - Eject and try another disc")
        print(" [Q] - Quit script")

        choice = input("\nChoose an option: ").lower()

        if choice == 'y':
            pass # Keep selected_ids as they are
        elif choice == 's':
            manual_input = input("Enter the IDs you want to rip, separated by commas: ")
            # Clean up input (remove spaces, split by comma)
            selected_ids = [x.strip() for x in manual_input.split(',') if x.strip().isdigit()]
        elif choice == 'e':
            print(f"Ejecting {DRIVE_LETTER}...")
            windows_native_eject(DRIVE_LETTER)
            return True # Loops back to wait for next disc
        elif choice == 'q':
            return "STOP"
        else:
            print("Invalid choice. Skipping this disc.")
            return True

    if not selected_ids:
        print("\n[!] No titles selected for ripping. Skipping.")
        return True

    # --- Disc Naming Logic ---
    name_match = re.search(r'CINFO:2,0,"(.+?)"', raw_info)
    disc_title = re.sub(r'[\\/*?:"<>|]', "", name_match.group(1)).strip() if name_match else f"Disc_{int(time.time())}"
    target_folder = os.path.join(BASE_OUTPUT_DIR, disc_title)
    if not os.path.exists(target_folder): os.makedirs(target_folder)

    # --- Execute Rip ---
    print(f"\nStarting Rip for IDs ({','.join(selected_ids)}): {disc_title}")
    start_rip = time.perf_counter()

    total_titles = len(selected_ids)
    print(f"\nStarting Rip for {total_titles} titles: {disc_title}")

    for index, tid in enumerate(selected_ids, start=1):
        print(f" >>> Ripping Title {tid}... ", end="", flush=True)

        # String-style command with your 2.5GB cache
        rip_cmd = f'"{MAKEMKV_BIN}" -r mkv disc:{DRIVE_INDEX} {tid} "{target_folder}" --cache={CACHE_SIZE} --minlength={MIN_LENGTH}'

        if not debug_mode:
            start_rip_title = time.perf_counter() # Start title timer

            # Run the command
            result = subprocess.run(rip_cmd, shell=True, capture_output=True, text=True)

            # FIX: Use start_rip_title here so it calculates the time for THIS title only
            rip_title_duration = time.perf_counter() - start_rip_title
            mt, st = divmod(rip_title_duration, 60)

            if result.returncode == 0:
                print(f"DONE in {int(mt)}m {int(st)}s.")
                progress_str = f"Ripped Title {index}/{total_titles}"
                send_ha_notification(disc_title, progress_str,300)
            else:
                print("FAILED")
                print(f"[!] Error Log: {result.stderr}")
        else:
            print("\n" + "="*20 + " DEBUG MODE " + "="*20)
            print(f"\n[EXEC]: {rip_cmd}")
            subprocess.run(rip_cmd, shell=True)

    end_rip = time.perf_counter()
    rip_duration = end_rip - start_rip
    m, s = divmod(rip_duration, 60)
    print(f"\n[SUCCESS] Total Rip process finished in {int(m)}m {int(s)}s.")

    # Fire the notification to Home Assistant before ejecting
    send_ha_notification(disc_title, "Ripped. Please Swap Disc")

    print(f"\nRip finished. Force Ejecting {DRIVE_LETTER}...")
    windows_native_eject(DRIVE_LETTER)
    return True

def countdown_timer(seconds):
    """Displays a countdown timer in the console."""
    print(f"\n[WAIT] Waiting {seconds} seconds for disc swap...")
    for i in range(seconds, 0, -1):
        # \r allows us to overwrite the same line in the terminal
        sys.stdout.write(f"\rNext scan starting in: {i:2d} seconds... (Press Ctrl+C to stop)")
        sys.stdout.flush()
        time.sleep(1)
    print("\n")

def clear_terminal():
    # 'cls' is for Windows, 'clear' is for Linux/Mac
    os.system('cls' if os.name == 'nt' else 'clear')

def smart_swap_wait(seconds, poll_interval=10):
    """
    Waits for a disc swap by polling the drive every 'poll_interval' seconds.
    The number of retries is (seconds // poll_interval).
    """
    # Calculate retries based on your logic (e.g., 60 // 5 = 12)
    max_retries = seconds // poll_interval

    print(f"\n[WAIT] Waiting up to {seconds}s for disc (Polling every {poll_interval}s)")
    print(f"[*] Maximum retries: {max_retries}")

    for attempt in range(1, max_retries + 1):
        # Calculate remaining time for the display
        remaining = seconds - ((attempt - 1) * poll_interval)

        sys.stdout.write(f"\rAttempt {attempt}/{max_retries} | ~{remaining:2d}s remaining... [Checking Drive]   ")
        sys.stdout.flush()

        # 1. Quick low-level check for disc presence
        # We target disc:INDEX specifically to avoid scanning other system drives
        check_cmd = [MAKEMKV_BIN, "-r", "info", f"disc:{DRIVE_INDEX}"]
        check = subprocess.run(check_cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)

        # 2. Check if the Volume Name (CINFO:2) is present in the output
        if "CINFO:2,0" in check.stdout:
            print(f"\n[!] Disc detected on attempt {attempt}! Starting rip...")
            return True

        # 3. Wait for the interval before trying again
        time.sleep(poll_interval)

    print(f"\n[!] Reached {max_retries} attempts without detecting a disc.")
    return False


def send_ha_notification(discName, message, timeout=60):
    """Sends a silent webhook to Home Assistant. Fails silently on any error."""

    payload = {
        "disk_name": discName,
        "status": message,
        "custom_timeout": timeout
    }
    try:
        # We set a short timeout so the script doesn't hang if HA is offline
        requests.post(HA_WEBHOOK_URL, json=payload, timeout=2)
    except:
        # Ignore all connection errors, timeouts, or DNS issues
        pass


if __name__ == "__main__":
    clear_terminal()

    # 1. Set your preferred defaults here
    is_debug = False
    is_verify = False  # Good to keep on for your ASUS drive
    is_progress = False  # You liked the visual feedback

    # 2. The Argument Loop: Overwrites defaults if flags are present
    for arg in sys.argv:
        # Boolean Flags (On/Off)
        if arg == "--debug":
            is_debug = True
        elif arg == "--no-debug":
            is_debug = False
        elif arg == "--verify-notifications":
            send_ha_notification("--verify-notifications", "Exiting")
            sys.exit(0)
        elif arg == "--verify":
            is_verify = True
        elif arg == "--no-verify":
            is_verify = False
        elif arg == "--progress":
            is_progress = True
        elif arg == "--no-progress":
            is_progress = False

        # Value Overrides (Key=Value)
        elif arg.startswith("--cache="):
            CACHE_SIZE = arg.split("=")[1]
        elif arg.startswith("--min="):
            MIN_LENGTH_ISO = arg.split("=")[1]
        elif arg.startswith("--max="):
            MAX_LENGTH_ISO = arg.split("=")[1]
        elif arg.startswith("--swap="):
            SWAP_DELAY_ISO = arg.split("=")[1]
        elif arg.startswith("--url="):
            HA_WEBHOOK_URL = arg.split("=")[1]

    # 3. Recalculate seconds based on final ISO strings
    MIN_LENGTH = iso_to_seconds(MIN_LENGTH_ISO)
    MAX_LENGTH = iso_to_seconds(MAX_LENGTH_ISO)
    SWAP_DELAY = iso_to_seconds(SWAP_DELAY_ISO)

    # Detect drive ONCE or inside the loop if you expect the drive to move
    DRIVE_INDEX, DRIVE_LETTER = get_drive_info()

    if DRIVE_INDEX is None:
        print("[CRITICAL] No optical drive detected! Please check your connection.")
        sys.exit(1)  # Exit the script instead of looping errors

    print(f"AUTO-RIPPER ACTIVE\nDrive: {DRIVE_LETTER} (Index {DRIVE_INDEX})\n" + "=" * 40)

    try:
        while True:
            result = rip_disc(verify_mode=is_verify, debug_mode=is_debug)
            if result == "STOP":
                break

            # Wait for user to swap disc
            smart_swap_wait(SWAP_DELAY)
    except KeyboardInterrupt:
        print("\nUser stopped script.")