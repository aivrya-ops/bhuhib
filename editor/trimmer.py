"""
Silence-based trimmer using pydub.
Detects and removes silent sections from a video clip.
"""
from __future__ import annotations

import os
import tempfile
from typing import List, Tuple

from pydub import AudioSegment
from pydub.silence import detect_nonsilent
from moviepy.editor import VideoFileClip, concatenate_videoclips


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
    # Export audio to a temp wav so pydub can analyse it
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        clip.audio.write_audiofile(tmp_path, logger=None)
        audio = AudioSegment.from_wav(tmp_path)
    finally:
        os.unlink(tmp_path)

    # Find non-silent ranges  →  list of [start_ms, end_ms]
    non_silent: List[Tuple[int, int]] = detect_nonsilent(
        audio,
        min_silence_len=min_silence_ms,
        silence_thresh=silence_thresh_db,
    )

    if not non_silent:
        print("  [trimmer] No non-silent segments found — returning original clip.")
        return clip

    # Add padding so cuts don't feel abrupt
    duration_ms = len(audio)
    padded: List[Tuple[float, float]] = []
    for start_ms, end_ms in non_silent:
        s = max(0, start_ms - padding_ms) / 1000.0
        e = min(duration_ms, end_ms + padding_ms) / 1000.0
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
    return concatenate_videoclips(sub_clips)
