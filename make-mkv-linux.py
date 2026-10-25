import subprocess
import time
import os
import sys
import re
import threading
import ctypes
import requests
from tqdm import tqdm

# --- Platform Configuration ---
IS_WINDOWS = sys.platform.startswith('win')

# --- Configuration (Adjust paths for Linux/Mini PC vs Windows) ---
if IS_WINDOWS:
    MAKEMKV_BIN = r"C:\Program Files (x86)\MakeMKV\makemkvcon.exe"
    BASE_OUTPUT_DIR = r"D:\Video"
else:
    # Standard Linux paths (adjust if installed elsewhere, e.g., via Flatpak or custom prefix)
    MAKEMKV_BIN = "/usr/bin/makemkvcon"
    BASE_OUTPUT_DIR = os.path.expanduser("~/Videos/Rips")

# --- Title Filters (ISO-8601 Format) ---
MIN_LENGTH_ISO = "PT30M"
MAX_LENGTH_ISO = "PT1H15M"
INFO_TIMEOUT_ISO = "PT10M00S"

# --- Delay Configuration ---
SWAP_DELAY_ISO = "PT1M"  # 1 Minute

# --- Notification Configuration ---
HA_WEBHOOK_URL = os.getenv("HA_WEBHOOK_URL", "http://surbey-mini.local:8123/api/webhook/rip_status_wh")

# Configured with a 2.5GB cache (--cache=2560) to maximize read speeds
CACHE_SIZE = 2560

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


def get_subproc_flags():
    """Returns platform-specific subprocess flags to hide terminal windows on Windows."""
    if IS_WINDOWS:
        return {"creationflags": 0x08000000} # CREATE_NO_WINDOW
    return {}

def get_drive_info():
    """Scans for a drive; returns (index, identifier) or (None, None) if not found."""
    try:
        cmd = [MAKEMKV_BIN, "-r", "info", "dev:list"]
        result = subprocess.run(cmd, capture_output=True, text=True, **get_subproc_flags())

        search_name = TARGET_DRIVE_NAME if TARGET_DRIVE_NAME else ""

        if IS_WINDOWS:
            if search_name:
                pattern = rf'DRV:(\d+),.*?"{re.escape(search_name)}.*?",".*?","([A-Z]:)"'
            else:
                pattern = r'DRV:(\d+),.*?,.*?,.*?"([A-Z]:)"'
        else:
            # Linux output format for makemkvcon dev:list typically uses device nodes like /dev/sr0
            if search_name:
                pattern = rf'DRV:(\d+),.*?"{re.escape(search_name)}.*?",".*?","(/dev/\w+)"'
            else:
                pattern = r'DRV:(\d+),.*?,.*?,.*?"(/dev/\w+)"'

        match = re.search(pattern, result.stdout)

        if match:
            return match.group(1), match.group(2)

    except Exception as e:
        print(f"[!] Drive detection error: {e}")

    return None, None

def native_eject(identifier):
    """Cross-platform tray eject mechanism."""
    if IS_WINDOWS:
        IOCTL_STORAGE_EJECT_MEDIA = 0x2D4808
        device_path = f"\\\\.\\{identifier.strip(':')}:"
        handle = ctypes.windll.kernel32.CreateFileW(device_path, 0x80000000, 0x01 | 0x02, None, 3, 0, None)
        if handle != -1:
            ctypes.windll.kernel32.DeviceIoControl(handle, IOCTL_STORAGE_EJECT_MEDIA, None, 0, None, 0, ctypes.byref(ctypes.c_ulong()), None)
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    else:
        # Linux native eject utility command
        try:
            subprocess.run(["eject", identifier], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

def format_seconds_to_iso(seconds):
    h, m = seconds // 3600, (seconds % 3600) // 60
    parts = ["PT"]
    if h > 0: parts.append(f"{h}H")
    if m > 0: parts.append(f"{m}M")
    return "".join(parts) if len(parts) > 1 else "PT0S"

def get_raw_data_with_progress():
    raw_info = ""
    print(f"[{time.strftime('%H:%M:%S')}] Querying Drive (Index:{DRIVE_INDEX} / {DRIVE_IDENTIFIER})...")
    start_info = time.perf_counter()
    stop_timer = False

    def stopwatch():
        with tqdm(total=0, desc="Scanning Disc Info", bar_format='{l_bar}{bar}| {elapsed}', leave=False) as pbar:
            while not stop_timer:
                pbar.update(0)
                time.sleep(0.1)

    timer_thread = threading.Thread(target=stopwatch)
    timer_thread.start()

    try:
        cmd = [
            MAKEMKV_BIN, "-r", "info", f"disc:{DRIVE_INDEX}",
            f"--minlength={MIN_LENGTH}"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=INFO_TIMEOUT, **get_subproc_flags())
        raw_info = result.stdout
    except Exception as e:
        print(f"\n[!] Error during scan: {e}")
    finally:
        stop_timer = True
        timer_thread.join()

    end_info = time.perf_counter()
    duration = end_info - start_info
    print(f"[*] Info scan completed in {duration:.2f} seconds.")
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

    titles = re.findall(r'TINFO:(\d+),9,0,"(\d+:\d+:\d+)"', raw_info)
    selected_ids = [t[0] for t in titles if MIN_LENGTH <= (lambda x: int(x[0])*3600 + int(x[1])*60 + int(x[2]))(t[1].split(':')) <= MAX_LENGTH]

    show_detailed_probe(raw_info)
    if verify_mode:
        print(f"\nCurrently selected based on filters: {', '.join(selected_ids) if selected_ids else 'None'}")
        print("-" * 30)
        print(" [Y] - Proceed with current selection")
        print(" [S] - Manually select IDs (e.g. 0,1,3)")
        print(" [E] - Eject and try another disc")
        print(" [Q] - Quit script")

        choice = input("\nChoose an option: ").lower()

        if choice == 'y':
            pass
        elif choice == 's':
            manual_input = input("Enter the IDs you want to rip, separated by commas: ")
            selected_ids = [x.strip() for x in manual_input.split(',') if x.strip().isdigit()]
        elif choice == 'e':
            print(f"Ejecting {DRIVE_IDENTIFIER}...")
            native_eject(DRIVE_IDENTIFIER)
            return True
        elif choice == 'q':
            return "STOP"
        else:
            print("Invalid choice. Skipping this disc.")
            return True

    if not selected_ids:
        print("\n[!] No titles selected for ripping. Skipping.")
        return True

    name_match = re.search(r'CINFO:2,0,"(.+?)"', raw_info)
    disc_title = re.sub(r'[\\/*?:"<>|]', "", name_match.group(1)).strip() if name_match else f"Disc_{int(time.time())}"
    target_folder = os.path.join(BASE_OUTPUT_DIR, disc_title)
    if not os.path.exists(target_folder): os.makedirs(target_folder)

    print(f"\nStarting Rip for IDs ({','.join(selected_ids)}): {disc_title}")
    start_rip = time.perf_counter()

    total_titles = len(selected_ids)

    for index, tid in enumerate(selected_ids, start=1):
        print(f" >>> Ripping Title {tid}... ", end="", flush=True)

        rip_cmd = f'"{MAKEMKV_BIN}" -r mkv disc:{DRIVE_INDEX} {tid} "{target_folder}" --cache={CACHE_SIZE} --minlength={MIN_LENGTH}'

        if not debug_mode:
            start_rip_title = time.perf_counter()
            result = subprocess.run(rip_cmd, shell=True, capture_output=True, text=True)
            rip_title_duration = time.perf_counter() - start_rip_title
            mt, st = divmod(rip_title_duration, 60)

            if result.returncode == 0:
                print(f"DONE in {int(mt)}m {int(st)}s.")
                progress_str = f"Ripped Title {index}/{total_titles}"
                send_ha_notification(disc_title, progress_str, 300)
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

    send_ha_notification(disc_title, "Ripped. Please Swap Disc")

    print(f"\nRip finished. Force Ejecting {DRIVE_IDENTIFIER}...")
    native_eject(DRIVE_IDENTIFIER)
    return True

def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')

def smart_swap_wait(seconds, poll_interval=10):
    max_retries = seconds // poll_interval

    print(f"\n[WAIT] Waiting up to {seconds}s for disc (Polling every {poll_interval}s)")
    print(f"[*] Maximum retries: {max_retries}")

    for attempt in range(1, max_retries + 1):
        remaining = seconds - ((attempt - 1) * poll_interval)

        sys.stdout.write(f"\rAttempt {attempt}/{max_retries} | ~{remaining:2d}s remaining... [Checking Drive]   ")
        sys.stdout.flush()

        check_cmd = [MAKEMKV_BIN, "-r", "info", f"disc:{DRIVE_INDEX}"]
        check = subprocess.run(check_cmd, capture_output=True, text=True, **get_subproc_flags())

        if "CINFO:2,0" in check.stdout:
            print(f"\n[!] Disc detected on attempt {attempt}! Starting rip...")
            return True

        time.sleep(poll_interval)

    print(f"\n[!] Reached {max_retries} attempts without detecting a disc.")
    return False

def send_ha_notification(discName, message, timeout=60):
    payload = {
        "disk_name": discName,
        "status": message,
        "custom_timeout": timeout
    }
    try:
        requests.post(HA_WEBHOOK_URL, json=payload, timeout=2)
    except:
        pass


if __name__ == "__main__":
    clear_terminal()

    is_debug = False
    is_verify = False
    is_progress = False

    for arg in sys.argv:
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

    MIN_LENGTH = iso_to_seconds(MIN_LENGTH_ISO)
    MAX_LENGTH = iso_to_seconds(MAX_LENGTH_ISO)
    SWAP_DELAY = iso_to_seconds(SWAP_DELAY_ISO)

    DRIVE_INDEX, DRIVE_IDENTIFIER = get_drive_info()

    if DRIVE_INDEX is None:
        print("[CRITICAL] No optical drive detected! Please check your connection.")
        sys.exit(1)

    print(f"AUTO-RIPPER ACTIVE\nDrive: {DRIVE_IDENTIFIER} (Index {DRIVE_INDEX})\n" + "=" * 40)

    try:
        while True:
            result = rip_disc(verify_mode=is_verify, debug_mode=is_debug)
            if result == "STOP":
                break
            smart_swap_wait(SWAP_DELAY)
    except KeyboardInterrupt:
        print("\nUser stopped script.")