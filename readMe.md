Auto-Ripper: MakeMKV Automation Script

This script provides a high-performance, automated workflow for archiving physical media using a Blu-ray/DVD drive. It is optimized for television series, ensuring episodes are captured while skipping unwanted "junk" titles like trailers and bonus features.

## Key Features

* **Dynamic Argument Overrides**: Change any timing or filtering setting on-the-fly without editing the source code.
* **Smart Disc Detection**: Polls the hardware every 5 seconds to detect a new disc swap immediately, rather than using a static sleep timer.
* **Performance Optimized**: Configured with a **2.5GB cache** (`--cache=2560`) to maximize read speeds and reduce drive wear.
* **Precision Filtering**: Uses ISO-8601 duration strings to define exact "rip windows," ensuring you catch 42-minute dramas while ignoring shorter trailers.
* **Home Assistant Integration**: Sends a silent webhook notification to your dashboard once a rip is complete.
* **Movie Mode Support**: Choose between series mode (folder-per-disc) or movie mode (flat output) with auto-prompt options.

## Usage & Arguments

The script now supports a robust argument loop. You can use boolean flags to toggle features or key-value pairs to override defaults.

### Boolean Flags
* `--verify`: (Default: False) Shows a **PROBE REPORT** and pauses for approval before ripping.
* `--no-verify`: (Default: True) Disable verification prompt.
* `--progress`: (Default: False) Displays a progress bar during disc info scanning.
* `--debug`: (Default: False) Prints the exact `makemkvcon` commands being executed.
* `--overwrite`: (Default: False) Overwrite existing output files.
* `--no-overwrite`: (Default: True) Preserve existing files (safe mode).
* `--movie`: (Default: series) Enable movie mode - flat file output without subfolders.
* `--no-movie`: Forces series mode - creates subfolders per disc.
* `--movie-auto`: Enables auto mode - skips all name/year prompts, uses disc title directly.
* `--no-movie-auto`: Disables auto mode - shows prompts (default when --movie used).
* `--verify-notifications`: Sends test notification and exits.

### Value Overrides
MakeMKV Settings:
* `--cache=X`: Change the cache size of MakeMKV.

Override your hardcoded constants using the `PT` (ISO-8601) format:
* `--min=PT[X]M`: Minimum title length to rip (e.g., `--min=PT20M`).
* `--max=PT[X]H`: Maximum title length to rip (e.g., `--max=PT4H`).
* `--swap=PT[X]M`: How long to wait for a disc swap before timing out (e.g., `--swap=PT5M`).

Home Assistant Integration for Notification
* `--url=[URL]`: Temporarily change the Home Assistant Webhook URL.

### Output Modes

**Series Mode** (default): Creates a subfolder per disc, files go inside
```bash
D:/Video/
  └── Equilibrium/
      └── title_t00.mkv
      └── title_t01.mkv
```

**Movie Mode** (--movie): Flat output directly to BASE_OUTPUT_DIR, single file named `{disc_title} - ({year})`
```bash
D:/Video/
  └── Equilibrium - (2004).mkv
```

## Execution Examples

```bash
# Standard run with your default 30m-1h window
python make-mkv.py

# Archiving shorter sitcoms or episodes under 30 minutes
python make-mkv.py --min=PT15M --no-verify

# Ripping a movie or "Season Play All" title
python make-mkv.py --max=PT5H --progress

# Movie mode: flat output without subfolders
python make-mkv.py --movie

# Movie mode with auto (skip name/year prompts)
python make-mkv.py --movie-auto

# Force series mode (explicit)
python make-mkv.py --no-movie

# Test webhook notifications
python make-mkv.py --verify-notifications
```

## Configuration

The script maintains the following defaults for local file management:
* **Base Directory**: Configure via `BASE_OUTPUT_DIR` variable in the script.
* **Drive Target**: Specify via `TARGET_DRIVE_NAME` variable (leave empty to auto-detect).
* **Home Assistant URL**: Set via environment variable `HA_WEBHOOK_URL` or override with `--url` flag.
* **Mathematical Precision**: All timing and size reports are displayed as decimals for maximum accuracy.

## Requirements

* **Hardware**: Blu-Ray/DVD Drive (Internal or External).
* **Dependencies**: `requests`, `tqdm`, `pytest` (for testing).
* **Software**: MakeMKV installed at `C:\Program Files (x86)\MakeMKV\`.

## Testing

Run unit tests with pytest to validate show_detailed_probe functionality:

```bash
. .venv/bin/activate
python -m pytest test_make_mkvtv.py -v
```

Tests use actual sample files from `info-samples/` directory.
