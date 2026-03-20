"""
Intro / outro overlay.
Prepends and/or appends existing video clips to the main clip.
"""
from __future__ import annotations

from moviepy.editor import VideoFileClip, concatenate_videoclips


def _load_and_match(clip_path: str, target: VideoFileClip) -> VideoFileClip:
    """Load overlay clip and resize/crop to match *target* dimensions."""
    ov = VideoFileClip(clip_path)
    # Resize to match target resolution
    if ov.size != target.size:
        ov = ov.resize(target.size)
    return ov


def add_intro_outro(
    main_clip: VideoFileClip,
    intro_path: str | None,
    outro_path: str | None,
) -> VideoFileClip:
    """Concatenate intro + main_clip + outro and return the combined clip."""
    parts = []

    if intro_path:
        print(f"  [overlay] Adding intro: {intro_path}")
        intro = _load_and_match(intro_path, main_clip)
        parts.append(intro)

    parts.append(main_clip)

    if outro_path:
        print(f"  [overlay] Adding outro: {outro_path}")
        outro = _load_and_match(outro_path, main_clip)
        parts.append(outro)

    if len(parts) == 1:
        return main_clip

    return concatenate_videoclips(parts, method="compose")
