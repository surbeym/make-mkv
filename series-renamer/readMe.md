# Universal Disc Renamer

A Python-based utility designed to automate the consolidation and renaming of TV series episodes from physical disc rips. It scans source folders (like `BUCK_ROGERS_DISC1`), sequences the episodes (e.g., `S01E01`, `S01E02`), and moves or copies them to a centralized directory.

---

## 🚀 Features

* **Smart Folder Filtering:** Quickly isolate specific folders using keywords like "DISC", "SIDE", or " D".
* **Sequential Numbering:** Automatically calculates and suggests the next episode number based on the previous folder's count.
* **Collision Handling:** Detects duplicate episode numbers (common in double-sided discs) and prompts for a custom suffix label.
* **Dry Run & Review:** Displays a formatted table of all proposed changes and performs a **disk space check** before any files are processed.
* **Logging:** Maintains a detailed `rename_log.txt` in the destination folder to track every file move or copy.
* **Cleanup:** Includes an optional feature to delete empty source folders after a "Move" operation is completed.

---

## 🛠️ Requirements

* **Python 3.x**
* **Operating System:** Windows (The script defaults to a `D:/Batched` output path).

---

## 📂 How It Works

1.  **Gather Info:** The script prompts for a folder filter, the output series name, and the season number.
2.  **Queueing:** It identifies matching folders and allows the user to set or confirm the starting episode for each disc.
3.  **Review:** A visual table displays the mapping of `Source Folder` to `New Filename`.
4.  **Execute:** The user chooses to **Copy** (safer), **Move** (faster/saves space), or **Abort** the operation.

---

## 📖 Usage

1.  Place `rename_tv-series.py` in the directory containing your disc folders.
2.  Run list directory
    ```
    ls
    LastWrite    Time    Length Name  
    2026-04-05   4:14 PM        GOSSIP_GIRL_SEASON_3_DISC_1
    2026-04-05   3:10 PM        GOSSIP_GIRL_SEASON_3_DISC_2
    2026-04-05   2:32 PM        GOSSIP_GIRL_SEASON_3_DISC_3
    2026-04-05   1:46 PM        GOSSIP_GIRL_SEASON_3_DISC_4
    2026-04-05   1:22 PM        GOSSIP_GIRL_SEASON_3_DISC_5
    2026-04-05   3:22 PM        GOSSIP_GIRL_SEASON_4_DISC_1
    2026-04-05   3:22 PM   5940 rename_tv-series.py
    ```
3.  Run the script:
    ```bash
    python rename_tv-series.py
    ```
4.  Follow the interactive prompts:
    * **Folder Filter:** Enter the keyword to find your folders (e.g., `GOSSIP_GIRL_SEASON_3`).
    * **Output Series Name:** Enter how the files should be named (e.g., `GOSSIP_GIRL`).
    * **Season Number:** Enter the season integer (defaults to `1`).
    ```
    Folder Filter (e.g., 'BUCK_ROGERS'): GOSSIP_GIRL_SEASON_3
    Output Series Name: GOSSIP_GIRL
    Season Number: 3
    Dry Run? (Y/n) [Default: Y]:
    ```
    * **Starting Episode:** Press **Enter** to accept the suggested number or type a new one.
    ```
    Processing Folder: GOSSIP_GIRL_SEASON_3_DISC_1
    Starting episode for this disc? (1):
    [Queued] title_t01.mkv -> GOSSIP_GIRL - S03E01.mkv
    [Queued] title_t02.mkv -> GOSSIP_GIRL - S03E02.mkv
    [Queued] title_t03.mkv -> GOSSIP_GIRL - S03E03.mkv
    [Queued] title_t04.mkv -> GOSSIP_GIRL - S03E04.mkv
    [Queued] title_t05.mkv -> GOSSIP_GIRL - S03E05.mkv
    
    Processing Folder: GOSSIP_GIRL_SEASON_3_DISC_2
      Starting episode for this disc? (6):
    
    ...
    
    =====================================================================================
    Total Size:                         28.67 GB
    Space Available on D:             1635.38 GB
    
    *** DRY RUN: No files will be moved yet. ***
    Ready to proceed? Choose [C]opy, [M]ove, or [A]bort:
    ```

---

## ⚠️ Important Notes

* **Destination:** By default, files are sent to `D:/Batched`. The script will create this folder if it does not exist.
* **File Format:** This script specifically targets and renames `.mkv` files.
* **Dry Run:** The script defaults to a Dry Run mode to prevent accidental file changes without review.

---

## 📜 Example Output

```text
=====================================================================================
SOURCE FOLDER                  | NEW FILENAME
-------------------------------------------------------------------------------------
GOSSIP_GIRL_SEASON_3_DISC_1    | GOSSIP_GIRL - S03E01.mkv
GOSSIP_GIRL_SEASON_3_DISC_1    | GOSSIP_GIRL - S03E02.mkv
GOSSIP_GIRL_SEASON_3_DISC_1    | GOSSIP_GIRL - S03E03.mkv
GOSSIP_GIRL_SEASON_3_DISC_1    | GOSSIP_GIRL - S03E04.mkv
GOSSIP_GIRL_SEASON_3_DISC_1    | GOSSIP_GIRL - S03E05.mkv
GOSSIP_GIRL_SEASON_3_DISC_2    | GOSSIP_GIRL - S03E06.mkv
GOSSIP_GIRL_SEASON_3_DISC_2    | GOSSIP_GIRL - S03E07.mkv
GOSSIP_GIRL_SEASON_3_DISC_2    | GOSSIP_GIRL - S03E08.mkv
GOSSIP_GIRL_SEASON_3_DISC_2    | GOSSIP_GIRL - S03E09.mkv
GOSSIP_GIRL_SEASON_3_DISC_2    | GOSSIP_GIRL - S03E10.mkv
GOSSIP_GIRL_SEASON_3_DISC_3    | GOSSIP_GIRL - S03E11.mkv
GOSSIP_GIRL_SEASON_3_DISC_3    | GOSSIP_GIRL - S03E12.mkv
GOSSIP_GIRL_SEASON_3_DISC_3    | GOSSIP_GIRL - S03E13.mkv
GOSSIP_GIRL_SEASON_3_DISC_3    | GOSSIP_GIRL - S03E14.mkv
GOSSIP_GIRL_SEASON_3_DISC_3    | GOSSIP_GIRL - S03E15.mkv
GOSSIP_GIRL_SEASON_3_DISC_4    | GOSSIP_GIRL - S03E16.mkv
GOSSIP_GIRL_SEASON_3_DISC_4    | GOSSIP_GIRL - S03E17.mkv
GOSSIP_GIRL_SEASON_3_DISC_4    | GOSSIP_GIRL - S03E18.mkv
GOSSIP_GIRL_SEASON_3_DISC_5    | GOSSIP_GIRL - S03E19.mkv
GOSSIP_GIRL_SEASON_3_DISC_5    | GOSSIP_GIRL - S03E20.mkv
GOSSIP_GIRL_SEASON_3_DISC_5    | GOSSIP_GIRL - S03E21.mkv
GOSSIP_GIRL_SEASON_3_DISC_5    | GOSSIP_GIRL - S03E22.mkv
=====================================================================================
Total Size:                         28.67 GB
Space Available on D:             1635.38 GB

*** DRY RUN: No files will be moved yet. ***
Ready to proceed? Choose [C]opy, [M]ove, or [A]bort: 
```