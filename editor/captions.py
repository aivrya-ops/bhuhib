"""
Auto-caption generator using OpenAI Whisper.
Transcribes audio, produces an SRT file, and burns subtitles into the clip.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import List

import whisper
from moviepy.editor import VideoFileClip


@dataclass
class CaptionConfig:
    whisper_model: str = "base"
    font: str = "Arial"
    font_size: int = 40
    color: str = "white"
    position: str = "bottom"   # top | center | bottom
    background: bool = True


def _seconds_to_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_srt(audio_path: str, model_name: str = "base") -> str:
    """Transcribe *audio_path* with Whisper and return SRT text."""
    print(f"  [captions] Loading Whisper model '{model_name}' …")
    model = whisper.load_model(model_name)
    print("  [captions] Transcribing …")
    result = model.transcribe(audio_path, word_timestamps=False)

    lines: List[str] = []
    for i, seg in enumerate(result["segments"], start=1):
        start = _seconds_to_srt_time(seg["start"])
        end = _seconds_to_srt_time(seg["end"])
        text = seg["text"].strip()
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")

    return "\n".join(lines)


def burn_captions(
    clip: VideoFileClip,
    cfg: CaptionConfig,
) -> VideoFileClip:
    """
    Burn subtitles into *clip* using FFmpeg's subtitles filter.
    Returns a new VideoFileClip with captions baked in.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Extract audio
        audio_path = os.path.join(tmpdir, "audio.wav")
        clip.audio.write_audiofile(audio_path, logger=None)

        # Generate SRT
        srt_content = generate_srt(audio_path, cfg.whisper_model)
        srt_path = os.path.join(tmpdir, "subs.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        # Write temp video (no audio needed for subtitle burn)
        tmp_in = os.path.join(tmpdir, "input.mp4")
        clip.write_videofile(tmp_in, audio=True, logger=None, verbose=False)

        # Position mapping
        pos_map = {"top": 10, "center": 50, "bottom": 90}
        margin_v = pos_map.get(cfg.position, 90)

        # Build ASS style overrides via force_style
        bg_flag = "1" if cfg.background else "0"
        force_style = (
            f"FontName={cfg.font},"
            f"FontSize={cfg.font_size},"
            f"PrimaryColour=&H00FFFFFF,"   # white text
            f"BackColour=&H80000000,"       # semi-transparent black bg
            f"BorderStyle={'3' if cfg.background else '1'},"
            f"MarginV={margin_v}"
        )

        # Escape the SRT path for FFmpeg on Linux
        srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:")

        tmp_out = os.path.join(tmpdir, "output.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-i", tmp_in,
            "-vf", f"subtitles='{srt_escaped}':force_style='{force_style}'",
            "-c:a", "copy",
            tmp_out,
        ]

        print("  [captions] Burning subtitles …")
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        result = VideoFileClip(tmp_out)
        # Load into memory so the temp dir can be deleted
        result = result.copy()

    return result
