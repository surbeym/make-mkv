import os
import shutil
from datetime import datetime

def get_input(prompt, default=""):
    # Ensures we always return a string for hit-enter support
    result = input(prompt).strip()
    return result if result else default

def get_free_space(path):
    total, used, free = shutil.disk_usage(os.path.abspath(path))
    return free

def consolidate_series():
    source_dir = os.getcwd()
    print(f"--- Universal Disc Renamer (Final Review Edition) ---")
    print(f"Working in: {source_dir}\n")

    # 1. Gather Initial Info
    filter_word = get_input("Folder Filter (e.g., 'BUCK_ROGERS'): ").upper()
    series_name = get_input("Output Series Name: ")
    season_num = get_input("Season Number: ", "1")
    is_dry_run = get_input("Dry Run? (Y/n) [Default: Y]: ", "y").lower() == 'y'

    destination = "D:/Batched"
    if not os.path.exists(destination):
        os.makedirs(destination)

    # 2. Find Folders
    items = sorted([d for d in os.listdir(source_dir) if os.path.isdir(os.path.join(source_dir, d))])
    disc_folders = [d for d in items if filter_word in d.upper() and ("DISC" in d.upper() or "SIDE" in d.upper() or " D" in d.upper())]

    if not disc_folders:
        print(f"\n[!] No folders found matching '{filter_word}'.")
        return

    pending_ops = []
    used_names = set()
    folders_to_clean = []
    total_size_bytes = 0
    next_suggested_ep = 1

    # 3. Queueing Logic
    for folder in disc_folders:
        print(f"\nProcessing Folder: {folder}")

        side_label = ""
        if "SIDE" in folder.upper():
            parts = folder.upper().split("SIDE")
            if len(parts) > 1:
                side_label = f"Side {parts[1].strip().strip('_')}"

        val = get_input(f"  Starting episode for this disc? ({next_suggested_ep}): ")

        if val == "":
            start_ep = next_suggested_ep
        else:
            try:
                start_ep = int(val)
            except ValueError:
                print("  Invalid input. Skipping folder.")
                continue

        folder_path = os.path.join(source_dir, folder)
        mkv_files = sorted([f for f in os.listdir(folder_path) if f.lower().endswith('.mkv')])

        if mkv_files:
            folders_to_clean.append(folder_path)

        for index, filename in enumerate(mkv_files):
            ep_num = start_ep + index
            base_new_name = f"{series_name} - S{int(season_num):02d}E{ep_num:02d}"
            final_new_name = f"{base_new_name}.mkv"

            if final_new_name in used_names:
                print(f"  [!] DUPLICATE Episode {ep_num} detected.")
                current_suggestion = side_label if side_label else "Alt"
                suffix = get_input(f"      Enter label (Suggested: '{current_suggestion}'): ", current_suggestion)
                final_new_name = f"{base_new_name} ({suffix}).mkv"

            used_names.add(final_new_name)
            src_file = os.path.join(folder_path, filename)
            dst_file = os.path.join(destination, final_new_name)

            total_size_bytes += os.path.getsize(src_file)
            pending_ops.append({
                'src_folder': folder,
                'old_name': filename,
                'new_name': final_new_name,
                'src_path': src_file,
                'dst_path': dst_file
            })
            print(f"  [Queued] {filename} -> {final_new_name}")

        next_suggested_ep = start_ep + len(mkv_files)

    if not pending_ops:
        print("Nothing to process."); return

    # 4. Review Table and Space Check
    total_gb_needed = total_size_bytes / (1024**3)
    free_gb_available = get_free_space(destination) / (1024**3)

    print(f"\n{'='*85}")
    print(f"{'SOURCE FOLDER':<30} | {'NEW FILENAME':<45}")
    print(f"{'-'*85}")
    for op in pending_ops:
        # Truncate folder name if too long for table
        folder_display = (op['src_folder'][:27] + '...') if len(op['src_folder']) > 30 else op['src_folder']
        print(f"{folder_display:<30} | {op['new_name']:<45}")
    print(f"{'='*85}")

    print(f"{'Total Size:':<30} {total_gb_needed:>10.2f} GB")
    print(f"{'Space Available on D:':<30} {free_gb_available:>10.2f} GB")

    if is_dry_run:
        print("\n*** DRY RUN: No files will be moved yet. ***")
        op_choice = get_input("Ready to proceed? Choose [C]opy, [M]ove, or [A]bort: ", "a").lower()
    else:
        op_choice = get_input("EXECUTE NOW? [C]opy, [M]ove, or [A]bort: ", "a").lower()

    if op_choice == 'a':
        print("Action cancelled."); return

    # 5. Execution
    log_path = os.path.join(destination, "rename_log.txt")
    verb = "COPIED" if op_choice == 'c' else "MOVED"

    print(f"\nProcessing {len(pending_ops)} files...")
    with open(log_path, 'a') as log:
        log.write(f"\n--- {verb} Session: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        for op in pending_ops:
            try:
                if op_choice == 'c':
                    shutil.copy2(op['src_path'], op['dst_path'])
                else:
                    shutil.move(op['src_path'], op['dst_path'])
                log.write(f"{verb}: {op['new_name']} | FROM: {op['src_path']}\n")
                print(f"  [OK] {op['new_name']}")
            except Exception as e:
                print(f"  [!] ERROR on {op['new_name']}: {e}")

    # 6. Cleanup
    if op_choice == 'm':
        cleanup = get_input(f"\nDelete empty source folders? (y/N): ", "n").lower()
        if cleanup == 'y':
            for folder_path in folders_to_clean:
                if not os.listdir(folder_path):
                    os.rmdir(folder_path)
                    print(f"  Deleted: {os.path.basename(folder_path)}")

    print(f"\nFinished! Log: {log_path}")

if __name__ == "__main__":
    consolidate_series()