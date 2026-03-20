#!/usr/bin/env python3
"""
Folder Watcher
==============
Watches a directory for new .mp4 / .mov / .mkv files and automatically
runs main.py on each one.

Usage:
    python watch.py [--watch-dir FOLDER] [--config config.yaml]
                    [--no-trim] [--no-captions] [--no-overlay] [--no-thumbnail]

Examples:
    python watch.py                          # watches ./inbox by default
    python watch.py --watch-dir C:\\Recordings
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

WATCHED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
POLL_INTERVAL = 5  # seconds between directory scans


def already_processed(path: Path, done_file: Path) -> bool:
    if not done_file.exists():
        return False
    processed = done_file.read_text(encoding="utf-8").splitlines()
    return str(path.resolve()) in processed


def mark_processed(path: Path, done_file: Path) -> None:
    with done_file.open("a", encoding="utf-8") as f:
        f.write(str(path.resolve()) + "\n")


def process(video: Path, extra_args: list[str]) -> None:
    cmd = [sys.executable, "main.py", str(video)] + extra_args
    print(f"\n[watcher] Processing: {video.name}")
    print(f"[watcher] Command: {' '.join(cmd)}\n")
    subprocess.run(cmd, check=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-process new videos in a folder")
    parser.add_argument("--watch-dir", default="inbox", help="Folder to watch (default: ./inbox)")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--no-trim", action="store_true")
    parser.add_argument("--no-captions", action="store_true")
    parser.add_argument("--no-overlay", action="store_true")
    parser.add_argument("--no-thumbnail", action="store_true")
    args = parser.parse_args()

    watch_dir = Path(args.watch_dir)
    watch_dir.mkdir(parents=True, exist_ok=True)

    done_file = watch_dir / ".processed"

    # Pass through any skip flags to main.py
    extra = ["--config", args.config]
    for flag in ("no_trim", "no_captions", "no_overlay", "no_thumbnail"):
        if getattr(args, flag):
            extra.append(f"--{flag.replace('_', '-')}")

    print(f"[watcher] Watching {watch_dir.resolve()} for new videos …")
    print("[watcher] Press Ctrl+C to stop.\n")

    try:
        while True:
            for path in sorted(watch_dir.iterdir()):
                if path.suffix.lower() not in WATCHED_EXTENSIONS:
                    continue
                if already_processed(path, done_file):
                    continue
                # Wait until the file stops growing (i.e. copy/write is done)
                size_before = path.stat().st_size
                time.sleep(2)
                if path.stat().st_size != size_before:
                    continue  # still being written
                mark_processed(path, done_file)
                process(path, extra)
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\n[watcher] Stopped.")


if __name__ == "__main__":
    main()
