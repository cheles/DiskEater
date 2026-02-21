# 🍽 DiskEater

A fast, colorful terminal tool that shows you exactly what's eating your disk space on macOS.

DiskEater scans directories and displays results in a tree view — folders sorted by size (largest first), with top files listed inside each folder. It also provides a flat ranked summary of the biggest directories and files.

![Python](https://img.shields.io/badge/python-3.8+-blue) ![Platform](https://img.shields.io/badge/platform-macOS-lightgrey) ![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **Tree view** — folders and files displayed hierarchically, sorted by size
- **Flat ranking** — top N largest directories and files at a glance
- **Color-coded sizes** — red (≥10 GB), orange (≥1 GB), yellow (≥100 MB), green (≥10 MB)
- **Progress bars** — visual percentage indicators for each entry
- **Disk usage summary** — shows overall disk capacity and usage
- **Configurable depth** — control how deep the scan goes
- **Size filtering** — hide small items with `--min-size`
- **Hidden file support** — optionally include dotfiles/dotdirs
- **Exclusion lists** — skip directories like `node_modules` or `.git`
- **No dependencies** — pure Python 3, no pip installs needed

## Quick Start

```bash
# Clone the repo
git clone https://github.com/cheles/DiskEater.git
cd DiskEater

# Run it (scans home directory by default)
python3 diskeater.py
```

## Usage

```
python3 diskeater.py [path] [options]
```

| Option | Description | Default |
|---|---|---|
| `path` | Directory to scan | `~` (home) |
| `-d`, `--depth` | Max directory depth to scan | `3` |
| `-n`, `--top-files` | Number of top files shown per directory | `10` |
| `--min-size` | Minimum size to display (e.g. `1MB`, `500KB`, `1GB`) | `1MB` |
| `--no-color` | Disable colored output | off |
| `--hidden` | Include hidden files and directories | off |
| `--flat` | Show only the flat ranked list (skip tree view) | off |
| `--flat-top` | Number of entries in flat view | `30` |
| `--exclude` | Directory/file names to exclude | — |

## Examples

```bash
# Scan home directory, default settings
python3 diskeater.py

# Scan entire disk, only show items >= 1 GB
python3 diskeater.py / --min-size 1GB

# Scan Downloads folder, 2 levels deep
python3 diskeater.py ~/Downloads -d 2

# Show top 20 files per folder, include hidden files
python3 diskeater.py -n 20 --hidden

# Exclude node_modules and .git directories
python3 diskeater.py ~/Projects --exclude node_modules .git

# Flat view only — quick ranked list
python3 diskeater.py --flat --flat-top 50
```

## Sample Output

```
  ╔══════════════════════════════════════════════════════════════╗
  ║  🍽  DiskEater — Disk Space Analysis                        ║
  ╚══════════════════════════════════════════════════════════════╝

  Root:  /Users/you
  Total: 159.6 GB
  Depth: 2 levels

  Disk:  214.7 GB used / 228.3 GB total (94.0% full)  ████████████████████████████

  ├── 📁 Library/       109.0 GB   68.3%  ██████████████
  │   ├── 📁 Developer/      82.0 GB   51.4%  ██████████
  │   ├── 📁 Android/        14.4 GB    9.0%  ██
  ├── 📁 Apps/            48.8 GB   30.6%  ██████████
  │   ├── 📁 ProjectA/       26.5 GB   16.6%  ████
  │   ├── 📁 ProjectB/       21.2 GB   13.3%  ███

  ── Top 30 largest directories ──

    1.    109.0 GB   68.3%  ██████████████   Library/
    2.     82.0 GB   51.4%  ██████████       Library/Developer/
    3.     48.8 GB   30.6%  ██████████       Apps/
```

## Requirements

- Python 3.8+
- macOS (works on Linux too, but disk info display is macOS-optimized)
- No third-party packages required

## iOS Simulator Cleanup Commands

If DiskEater shows large usage under `~/Library/Developer/CoreSimulator`, these commands can free space and recover a broken simulator device set.

### Safer Cleanup (keep most setup)

```bash
# Quit Xcode + Simulator first
xcrun simctl shutdown all
xcrun simctl delete unavailable

rm -rf ~/Library/Developer/Xcode/DerivedData/*
rm -rf ~/Library/Developer/Xcode/Archives/*
rm -rf ~/Library/Developer/Xcode/iOS\ DeviceSupport/*
rm -rf ~/Library/Logs/CoreSimulator/*
rm -rf ~/Library/Developer/CoreSimulator/Caches/*
```

### Reset Broken Simulator Device Set

If you get:

"Use the device manager in Xcode or the simctl command line tool to either delete the device properly or erase contents and settings."

Run:

```bash
xcrun simctl shutdown all || true
killall -9 Simulator || true
killall -9 com.apple.CoreSimulator.CoreSimulatorService || true

rm -rf ~/Library/Developer/CoreSimulator/Devices
rm -f ~/Library/Developer/CoreSimulator/device_set.plist
rm -rf ~/Library/Logs/CoreSimulator/*

open -a Xcode
xcrun simctl list devices
```

If devices are still missing, run:

```bash
sudo xcode-select -switch /Applications/Xcode.app
sudo xcodebuild -runFirstLaunch
```

## License

MIT
