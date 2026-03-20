"""
MrBeast-style captions: word-by-word highlight using Whisper word timestamps.
Generates an ASS subtitle file where each word pops in bold yellow,
surrounded by white text + thick black stroke.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import List


@dataclass
class CaptionConfig:
    whisper_model: str = "small"
    font: str = "Impact"
    font_size: int = 72
    text_color: str = "white"           # default word color
    highlight_color: str = "yellow"     # active word color
    position: str = "bottom"           # top | center | bottom
    words_per_line: int = 4            # how many words shown at once
    uppercase: bool = True             # ALL CAPS like MrBeast


# ── ASS color helpers ─────────────────────────────────────────────────────────

def _hex_to_ass(color: str) -> str:
    """Convert a color name or '#RRGGBB' string to ASS &HAABBGGRR format."""
    named = {
        "white":  "FFFFFF", "yellow": "00FFFF",  # note: ASS is BGR not RGB
        "black":  "000000", "red":    "0000FF",
        "blue":   "FF0000", "green":  "00FF00",
        "orange": "0080FF", "cyan":   "FFFF00",
    }
    if color.lower() in named:
        bgr = named[color.lower()]
    elif color.startswith("#"):
        r, g, b = color[1:3], color[3:5], color[5:7]
        bgr = b + g + r
    else:
        bgr = "FFFFFF"
    return f"&H00{bgr}&"


def _ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


# ── ASS generation ────────────────────────────────────────────────────────────

_ASS_HEADER = """\
[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},{primary},{secondary},&H00000000&,&H80000000&,-1,0,0,0,100,100,0,0,1,6,2,{align},60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _build_ass(
    words: List[dict],
    cfg: CaptionConfig,
    video_width: int = 1920,
    video_height: int = 1080,
) -> str:
    """Build a full .ass subtitle file with per-word karaoke-style highlighting."""
    # Alignment: 2 = bottom-center, 8 = top-center, 5 = middle-center
    align_map = {"bottom": 2, "top": 8, "center": 5}
    align = align_map.get(cfg.position, 2)
    margin_v = 80 if cfg.position == "bottom" else 40

    primary = _hex_to_ass(cfg.text_color)
    secondary = _hex_to_ass(cfg.highlight_color)

    header = _ASS_HEADER.format(
        font=cfg.font,
        size=cfg.font_size,
        primary=primary,
        secondary=secondary,
        align=align,
        margin_v=margin_v,
    )

    events: List[str] = []
    n = len(words)
    step = cfg.words_per_line

    i = 0
    while i < n:
        group = words[i : i + step]
        group_start = group[0]["start"]
        group_end = group[-1]["end"]

        # Build one ASS event per word in the group — highlight active word
        for j, active_word in enumerate(group):
            seg_start = active_word["start"]
            seg_end = active_word["end"]

            parts = []
            for k, w in enumerate(group):
                text = w["word"].upper() if cfg.uppercase else w["word"]
                text = text.strip()
                if k == j:
                    # Active word: highlight color + slight scale-up
                    parts.append(
                        f"{{\\c{secondary}\\t(\\fscx115\\fscy115)}}{{\\fscx115\\fscy115}}{text}{{\\fscx100\\fscy100\\c{primary}}}"
                    )
                else:
                    parts.append(f"{{\\c{primary}}}{text}")

            line = " ".join(parts)
            events.append(
                f"Dialogue: 0,{_ass_time(seg_start)},{_ass_time(seg_end)},Default,,0,0,0,,{line}"
            )

        i += step

    return header + "\n".join(events) + "\n"


# ── public API ────────────────────────────────────────────────────────────────

def burn_captions(clip, cfg: CaptionConfig):
    """
    Transcribe *clip* with Whisper word timestamps and burn MrBeast-style
    word-by-word captions.  Returns a new VideoFileClip.
    """
    import whisper
    from moviepy.editor import VideoFileClip

    with tempfile.TemporaryDirectory() as tmpdir:
        # Extract audio
        audio_path = os.path.join(tmpdir, "audio.wav")
        clip.audio.write_audiofile(audio_path, logger=None)

        # Transcribe with word-level timestamps
        print(f"  [captions] Loading Whisper '{cfg.whisper_model}' …")
        model = whisper.load_model(cfg.whisper_model)
        print("  [captions] Transcribing with word timestamps …")
        result = model.transcribe(audio_path, word_timestamps=True)

        # Flatten all words
        words: List[dict] = []
        for seg in result["segments"]:
            for w in seg.get("words", []):
                words.append({
                    "word": w["word"],
                    "start": w["start"],
                    "end": w["end"],
                })

        if not words:
            print("  [captions] No words found — skipping captions.")
            return clip

        print(f"  [captions] Got {len(words)} words. Building ASS subtitles …")

        # Build ASS
        ass_content = _build_ass(words, cfg, clip.w, clip.h)
        ass_path = os.path.join(tmpdir, "subs.ass")
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(ass_content)

        # Write video to temp file
        tmp_in = os.path.join(tmpdir, "input.mp4")
        clip.write_videofile(tmp_in, audio=True, logger=None, verbose=False)

        tmp_out = os.path.join(tmpdir, "output.mp4")
        ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")

        cmd = [
            "ffmpeg", "-y",
            "-i", tmp_in,
            "-vf", f"ass='{ass_escaped}'",
            "-c:v", "libx264", "-crf", "16", "-preset", "slow",
            "-c:a", "copy",
            tmp_out,
        ]

        print("  [captions] Burning captions …")
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        result_clip = VideoFileClip(tmp_out)
        result_clip = result_clip.copy()

    return result_clip
