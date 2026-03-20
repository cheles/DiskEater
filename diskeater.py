#!/usr/bin/env python3
"""
DiskEater - macOS Disk Space Analyzer
Scans directories and reports what's consuming your disk space,
ordered by folders (largest first), then files within each folder.
"""

import os
import sys
import argparse
import time
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional


# ── ANSI colors ──────────────────────────────────────────────────────────────

class C:
    BOLD      = "\033[1m"
    DIM       = "\033[2m"
    RED       = "\033[91m"
    ORANGE    = "\033[38;5;208m"
    YELLOW    = "\033[93m"
    GREEN     = "\033[92m"
    CYAN      = "\033[96m"
    BLUE      = "\033[94m"
    MAGENTA   = "\033[95m"
    GRAY      = "\033[90m"
    RESET     = "\033[0m"
    BAR_FULL  = "\033[48;5;203m"
    BAR_EMPTY = "\033[48;5;236m"

    @staticmethod
    def disable():
        for attr in dir(C):
            if attr.isupper() and not attr.startswith("_"):
                setattr(C, attr, "")


# ── Helpers ──────────────────────────────────────────────────────────────────

def human_size(nbytes: float) -> str:
    """Convert bytes to a human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(nbytes) < 1024:
            if unit == "B":
                return f"{int(nbytes)} {unit}"
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} EB"


def size_color(nbytes: float) -> str:
    """Pick a color based on size magnitude."""
    if nbytes >= 10 * 1024**3:     # >= 10 GB
        return C.RED
    elif nbytes >= 1 * 1024**3:    # >= 1 GB
        return C.ORANGE
    elif nbytes >= 100 * 1024**2:  # >= 100 MB
        return C.YELLOW
    elif nbytes >= 10 * 1024**2:   # >= 10 MB
        return C.GREEN
    else:
        return C.DIM


def bar(fraction: float, width: int = 20) -> str:
    """Render a mini bar chart."""
    filled = int(fraction * width)
    empty = width - filled
    return f"{C.BAR_FULL}{' ' * filled}{C.RESET}{C.BAR_EMPTY}{' ' * empty}{C.RESET}"


def pct_str(fraction: float) -> str:
    p = fraction * 100
    if p >= 10:
        return f"{C.RED}{p:5.1f}%{C.RESET}"
    elif p >= 1:
        return f"{C.YELLOW}{p:5.1f}%{C.RESET}"
    else:
        return f"{C.DIM}{p:5.1f}%{C.RESET}"


# ── Data model ───────────────────────────────────────────────────────────────

@dataclass
class FileInfo:
    path: str
    size: int

@dataclass
class DirInfo:
    path: str
    own_files: list = field(default_factory=list)   # list[FileInfo]
    total_size: int = 0           # recursive total (files + subdirs)
    own_file_size: int = 0        # size of direct child files only
    num_files: int = 0
    num_dirs: int = 0
    error: bool = False


# ── Scanner ──────────────────────────────────────────────────────────────────

class DiskScanner:
    def __init__(self, root: str, max_depth: int = 3, top_n_files: int = 10,
                 min_size: int = 0, exclude: Optional[list] = None,
                 show_hidden: bool = False):
        self.root = os.path.abspath(root)
        self.max_depth = max_depth
        self.top_n_files = top_n_files
        self.min_size = min_size
        self.exclude = set(exclude or [])
        self.show_hidden = show_hidden
        self.scanned = 0
        self.errors = 0

    def _should_skip(self, name: str, full_path: str) -> bool:
        if not self.show_hidden and name.startswith("."):
            return True
        if name in self.exclude:
            return True
        # Skip some macOS system dirs that require SIP
        skip_paths = {"/System/Volumes", "/private/var/db", "/private/var/folders"}
        for sp in skip_paths:
            if full_path.startswith(sp):
                return True
        return False

    def scan(self) -> dict:
        """
        Walk the directory tree up to max_depth.
        Returns {path: DirInfo} for every scanned directory.
        """
        results = {}
        self._scan_dir(self.root, 0, results)
        return results

    def _scan_dir(self, path: str, depth: int, results: dict) -> int:
        """Recursively scan, returning total size of this directory."""
        self.scanned += 1
        if self.scanned % 500 == 0:
            print(f"\r  {C.DIM}Scanning... {self.scanned} directories{C.RESET}", end="", flush=True)

        info = DirInfo(path=path)
        total = 0

        try:
            entries = list(os.scandir(path))
        except PermissionError:
            info.error = True
            self.errors += 1
            results[path] = info
            return 0
        except OSError:
            info.error = True
            self.errors += 1
            results[path] = info
            return 0

        for entry in entries:
            if self._should_skip(entry.name, entry.path):
                continue

            try:
                if entry.is_symlink():
                    continue

                if entry.is_file(follow_symlinks=False):
                    try:
                        sz = entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
                    info.own_files.append(FileInfo(path=entry.path, size=sz))
                    info.own_file_size += sz
                    info.num_files += 1
                    total += sz

                elif entry.is_dir(follow_symlinks=False):
                    info.num_dirs += 1
                    if depth < self.max_depth:
                        sub_total = self._scan_dir(entry.path, depth + 1, results)
                        total += sub_total
                    else:
                        # Beyond max depth, just sum sizes quickly
                        sub_total = self._quick_size(entry.path)
                        total += sub_total
            except OSError:
                self.errors += 1
                continue

        info.total_size = total
        # Sort files by size descending, keep top N
        info.own_files.sort(key=lambda f: f.size, reverse=True)
        results[path] = info
        return total

    def _quick_size(self, path: str) -> int:
        """Quickly sum all file sizes under a directory (no detail tracking)."""
        total = 0
        try:
            for root, dirs, files in os.walk(path, followlinks=False):
                # Filter hidden
                if not self.show_hidden:
                    dirs[:] = [d for d in dirs if not d.startswith(".")]
                for f in files:
                    if not self.show_hidden and f.startswith("."):
                        continue
                    try:
                        total += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        pass
        except OSError:
            pass
        return total


# ── Reporter ─────────────────────────────────────────────────────────────────

class Reporter:
    def __init__(self, results: dict, root: str, top_n_files: int = 10,
                 min_size: int = 0, max_depth: int = 3):
        self.results = results
        self.root = root
        self.top_n_files = top_n_files
        self.min_size = min_size
        self.max_depth = max_depth

    def report(self):
        root_info = self.results.get(self.root)
        if not root_info:
            print(f"{C.RED}Error: Could not scan root directory.{C.RESET}")
            return

        grand_total = root_info.total_size
        if grand_total == 0:
            print(f"{C.YELLOW}No files found (directory may be empty or inaccessible).{C.RESET}")
            return

        # Gather first-level children
        self._print_header(grand_total)
        self._print_tree(self.root, grand_total, depth=0)

    def _print_header(self, grand_total: int):
        print()
        print(f"  {C.BOLD}{C.CYAN}╔══════════════════════════════════════════════════════════════╗{C.RESET}")
        print(f"  {C.BOLD}{C.CYAN}║{C.RESET}  {C.BOLD}🍽  DiskEater — Disk Space Analysis{C.RESET}                         {C.BOLD}{C.CYAN}║{C.RESET}")
        print(f"  {C.BOLD}{C.CYAN}╚══════════════════════════════════════════════════════════════╝{C.RESET}")
        print()
        print(f"  {C.BOLD}Root:{C.RESET}  {self.root}")
        print(f"  {C.BOLD}Total:{C.RESET} {C.RED}{C.BOLD}{human_size(grand_total)}{C.RESET}")
        print(f"  {C.BOLD}Depth:{C.RESET} {self.max_depth} levels")
        print()

        # Show disk usage info (macOS)
        try:
            st = os.statvfs(self.root)
            disk_total = st.f_blocks * st.f_frsize
            disk_free = st.f_bavail * st.f_frsize
            disk_used = disk_total - disk_free
            frac = disk_used / disk_total if disk_total else 0
            print(f"  {C.BOLD}Disk:{C.RESET}  {human_size(disk_used)} used / {human_size(disk_total)} total "
                  f"({frac*100:.1f}% full)  {bar(frac, 30)}")
            print()
        except OSError:
            pass

    def _print_tree(self, dir_path: str, grand_total: int, depth: int):
        info = self.results.get(dir_path)
        if not info:
            return

        # Collect child directories with their sizes
        child_dirs = []
        try:
            for entry_path, entry_info in self.results.items():
                if entry_path == dir_path:
                    continue
                parent = os.path.dirname(entry_path)
                if parent == dir_path:
                    child_dirs.append(entry_info)
        except:
            pass

        child_dirs.sort(key=lambda d: d.total_size, reverse=True)

        indent = "  " + "    " * depth
        connector_dir = "📁"
        connector_file = "📄"

        # Print child directories
        for i, child in enumerate(child_dirs):
            if child.total_size < self.min_size:
                continue

            fraction = child.total_size / grand_total if grand_total else 0
            sc = size_color(child.total_size)
            dirname = os.path.basename(child.path)

            is_last_dir = (i == len(child_dirs) - 1)
            tree_char = "└──" if is_last_dir and not info.own_files else "├──"

            print(f"{indent}{C.DIM}{tree_char}{C.RESET} {connector_dir} "
                  f"{C.BOLD}{dirname}/{C.RESET}"
                  f"  {sc}{human_size(child.total_size):>10}{C.RESET}"
                  f"  {pct_str(fraction)}"
                  f"  {bar(fraction, 15)}")

            if child.error:
                print(f"{indent}     {C.RED}⚠  Permission denied{C.RESET}")

            # Recurse into subdirectory
            if depth + 1 <= self.max_depth:
                self._print_tree(child.path, grand_total, depth + 1)

        # Print top files in this directory
        files_to_show = info.own_files[:self.top_n_files]
        files_to_show = [f for f in files_to_show if f.size >= self.min_size]

        if files_to_show:
            remaining = len(info.own_files) - len(files_to_show)
            remaining_size = sum(f.size for f in info.own_files[self.top_n_files:])

            for j, finfo in enumerate(files_to_show):
                fraction = finfo.size / grand_total if grand_total else 0
                sc = size_color(finfo.size)
                fname = os.path.basename(finfo.path)

                is_last = (j == len(files_to_show) - 1) and remaining == 0
                tree_char = "└──" if is_last else "├──"

                print(f"{indent}{C.DIM}{tree_char}{C.RESET} {connector_file} "
                      f"{fname}"
                      f"  {sc}{human_size(finfo.size):>10}{C.RESET}"
                      f"  {pct_str(fraction)}")

            if remaining > 0:
                print(f"{indent}{C.DIM}└── ... {remaining} more files "
                      f"({human_size(remaining_size)}){C.RESET}")


# ── Top-level summary (flat view) ───────────────────────────────────────────

def print_flat_summary(results: dict, root: str, top_n: int = 30, min_size: int = 0):
    """Print the largest directories as a flat sorted list."""
    root_info = results.get(root)
    if not root_info:
        return
    grand_total = root_info.total_size

    print()
    print(f"  {C.BOLD}{C.CYAN}── Top {top_n} largest directories ──{C.RESET}")
    print()

    all_dirs = [(p, d) for p, d in results.items() if d.total_size >= min_size and p != root]
    all_dirs.sort(key=lambda x: x[1].total_size, reverse=True)

    for i, (path, info) in enumerate(all_dirs[:top_n]):
        fraction = info.total_size / grand_total if grand_total else 0
        sc = size_color(info.total_size)
        rel = os.path.relpath(path, root)

        rank = f"{i+1:>3}."
        print(f"  {C.DIM}{rank}{C.RESET}  {sc}{human_size(info.total_size):>10}{C.RESET}"
              f"  {pct_str(fraction)}  {bar(fraction, 15)}"
              f"  {rel}/")

    # Largest files across all directories
    print()
    print(f"  {C.BOLD}{C.CYAN}── Top {top_n} largest files ──{C.RESET}")
    print()

    all_files = []
    for path, info in results.items():
        for f in info.own_files:
            if f.size >= min_size:
                all_files.append(f)

    all_files.sort(key=lambda f: f.size, reverse=True)

    for i, finfo in enumerate(all_files[:top_n]):
        fraction = finfo.size / grand_total if grand_total else 0
        sc = size_color(finfo.size)
        rel = os.path.relpath(finfo.path, root)

        rank = f"{i+1:>3}."
        print(f"  {C.DIM}{rank}{C.RESET}  {sc}{human_size(finfo.size):>10}{C.RESET}"
              f"  {pct_str(fraction)}  {bar(fraction, 15)}"
              f"  {rel}")

    print()


# ── Main ─────────────────────────────────────────────────────────────────────

def parse_size(s: str) -> int:
    """Parse a human-readable size string (e.g. '100MB') to bytes."""
    s = s.strip().upper()
    units = {"B": 1, "K": 1024, "KB": 1024, "M": 1024**2, "MB": 1024**2,
             "G": 1024**3, "GB": 1024**3, "T": 1024**4, "TB": 1024**4}
    for suffix, mult in sorted(units.items(), key=lambda x: -len(x[0])):
        if s.endswith(suffix):
            return int(float(s[:-len(suffix)]) * mult)
    return int(s)


def main():
    parser = argparse.ArgumentParser(
        description="🍽  DiskEater — Find out what's eating your disk space",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Scan home directory
  %(prog)s /                        # Scan entire disk
  %(prog)s ~/Downloads -d 2         # Scan Downloads, 2 levels deep
  %(prog)s / --min-size 1GB         # Only show items >= 1 GB
  %(prog)s -n 20 --hidden           # Show 20 files per dir, include hidden
        """)

    parser.add_argument("path", nargs="?", default=str(Path.home()),
                        help="Directory to scan (default: home directory)")
    parser.add_argument("-d", "--depth", type=int, default=3,
                        help="Max directory depth to scan (default: 3)")
    parser.add_argument("-n", "--top-files", type=int, default=10,
                        help="Number of top files to show per directory (default: 10)")
    parser.add_argument("--min-size", type=str, default="1MB",
                        help="Minimum size to display (e.g. 1MB, 500KB, 1GB; default: 1MB)")
    parser.add_argument("--no-color", action="store_true",
                        help="Disable colored output")
    parser.add_argument("--hidden", action="store_true",
                        help="Include hidden files/directories (dotfiles)")
    parser.add_argument("--flat", action="store_true",
                        help="Show flat list of largest dirs and files instead of tree")
    parser.add_argument("--flat-top", type=int, default=30,
                        help="Number of entries in flat view (default: 30)")
    parser.add_argument("--exclude", nargs="*", default=[],
                        help="Directory/file names to exclude (e.g. node_modules .git)")

    args = parser.parse_args()

    if args.no_color:
        C.disable()

    min_bytes = parse_size(args.min_size)
    target = os.path.abspath(os.path.expanduser(args.path))

    if not os.path.isdir(target):
        print(f"{C.RED}Error: '{target}' is not a directory.{C.RESET}")
        sys.exit(1)

    default_excludes = [".Spotlight-V100", ".fseventsd", ".Trashes",
                        ".DocumentRevisions-V100", ".TemporaryItems"]
    excludes = default_excludes + args.exclude

    print(f"\n  {C.DIM}Scanning {target} ...{C.RESET}")
    t0 = time.time()

    scanner = DiskScanner(
        root=target,
        max_depth=args.depth,
        top_n_files=args.top_files,
        min_size=0,  # collect everything; filter at display time
        exclude=excludes,
        show_hidden=args.hidden,
    )
    results = scanner.scan()
    elapsed = time.time() - t0

    # Clear scanning progress line
    print(f"\r  {C.DIM}Scanned {scanner.scanned} directories in {elapsed:.1f}s "
          f"({scanner.errors} permission errors){C.RESET}")

    if args.flat:
        print_flat_summary(results, target, top_n=args.flat_top, min_size=min_bytes)
    else:
        reporter = Reporter(results, target, top_n_files=args.top_files,
                            min_size=min_bytes, max_depth=args.depth)
        reporter.report()
        # Also show flat summary
        print_flat_summary(results, target, top_n=args.flat_top, min_size=min_bytes)


if __name__ == "__main__":
    main()
