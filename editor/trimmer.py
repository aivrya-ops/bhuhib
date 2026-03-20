"""
Silence-based trimmer using ffmpeg/numpy (no pydub dependency).
Detects and removes silent sections from a video clip.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from typing import List, Tuple

from moviepy.editor import VideoFileClip, concatenate_videoclips


def _detect_nonsilent_ffmpeg(
    wav_path: str,
    silence_thresh_db: int = -50,
    min_silence_ms: int = 700,
) -> List[Tuple[float, float]]:
    """Use ffmpeg silencedetect to find non-silent ranges. Returns list of (start_s, end_s)."""
    cmd = [
        "ffmpeg", "-i", wav_path,
        "-af", f"silencedetect=noise={silence_thresh_db}dB:d={min_silence_ms / 1000:.3f}",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stderr

    # Parse silence_start / silence_end pairs
    silence_ranges: List[Tuple[float, float]] = []
    silence_start = None
    for line in output.splitlines():
        if "silence_start" in line:
            try:
                silence_start = float(line.split("silence_start:")[1].split()[0])
            except (IndexError, ValueError):
                pass
        elif "silence_end" in line and silence_start is not None:
            try:
                silence_end = float(line.split("silence_end:")[1].split()[0])
                silence_ranges.append((silence_start, silence_end))
                silence_start = None
            except (IndexError, ValueError):
                pass

    # Get total duration
    duration = None
    for line in output.splitlines():
        if "Duration:" in line:
            try:
                t = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = t.split(":")
                duration = int(h) * 3600 + int(m) * 60 + float(s)
            except Exception:
                pass

    if duration is None:
        # fallback: probe the file
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", wav_path],
            capture_output=True, text=True,
        )
        try:
            duration = float(json.loads(probe.stdout)["format"]["duration"])
        except Exception:
            duration = 0.0

    # Convert silence ranges → non-silent ranges
    non_silent: List[Tuple[float, float]] = []
    cursor = 0.0
    for s_start, s_end in sorted(silence_ranges):
        if cursor < s_start:
            non_silent.append((cursor, s_start))
        cursor = s_end
    if cursor < duration:
        non_silent.append((cursor, duration))

    return non_silent


def trim_silence(
    clip: VideoFileClip,
    silence_thresh_db: int = -50,
    min_silence_ms: int = 700,
    padding_ms: int = 200,
) -> VideoFileClip:
    """
    Remove silent sections from *clip*.
    Returns a new VideoFileClip with silence stripped out.
    """
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        clip.audio.write_audiofile(tmp_path, logger=None)
        non_silent = _detect_nonsilent_ffmpeg(tmp_path, silence_thresh_db, min_silence_ms)
    finally:
        os.unlink(tmp_path)

    if not non_silent:
        print("  [trimmer] No non-silent segments found — returning original clip.")
        return clip

    # Add padding
    duration_s = clip.duration
    padded: List[Tuple[float, float]] = []
    for start_s, end_s in non_silent:
        s = max(0.0, start_s - padding_ms / 1000.0)
        e = min(duration_s, end_s + padding_ms / 1000.0)
        padded.append((s, e))

    # Merge overlapping segments
    merged: List[Tuple[float, float]] = [padded[0]]
    for s, e in padded[1:]:
        if s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    print(f"  [trimmer] Keeping {len(merged)} segment(s) out of original {clip.duration:.1f}s")

    sub_clips = [clip.subclip(s, e) for s, e in merged]

    # Apply crossfade transitions between cuts
    fade_s = min(0.15, padding_ms / 1000.0)
    if len(sub_clips) > 1:
        faded = [sub_clips[0].crossfadeout(fade_s)]
        for sc in sub_clips[1:-1]:
            faded.append(sc.crossfadein(fade_s).crossfadeout(fade_s))
        faded.append(sub_clips[-1].crossfadein(fade_s))
        return concatenate_videoclips(faded, padding=-fade_s, method="compose")

    return concatenate_videoclips(sub_clips)
