"""
Auto thumbnail generator.
Finds the sharpest/most visually interesting frame in the video,
then overlays bold title text MrBeast-style.
"""
from __future__ import annotations

import os
from typing import Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter


def _sharpness_score(frame: np.ndarray) -> float:
    """Laplacian variance — higher = sharper / more detail."""
    gray = np.mean(frame, axis=2)
    laplacian = (
        gray[:-2, 1:-1] + gray[2:, 1:-1] + gray[1:-1, :-2] + gray[1:-1, 2:]
        - 4 * gray[1:-1, 1:-1]
    )
    return float(np.var(laplacian))


def pick_best_frame(clip, num_candidates: int = 20) -> np.ndarray:
    """Sample *num_candidates* frames and return the sharpest one."""
    # Skip first and last 5% to avoid black frames
    start = clip.duration * 0.05
    end = clip.duration * 0.95
    times = np.linspace(start, end, num_candidates)

    best_frame = None
    best_score = -1.0
    for t in times:
        frame = clip.get_frame(t)
        score = _sharpness_score(frame)
        if score > best_score:
            best_score = score
            best_frame = frame

    return best_frame


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Word-wrap *text* to fit within *max_width* pixels."""
    words = text.split()
    lines: list[str] = []
    current = ""
    dummy = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(dummy)

    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_text_with_stroke(
    draw: ImageDraw.ImageDraw,
    pos: Tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int],
    stroke_fill: Tuple[int, int, int] = (0, 0, 0),
    stroke_width: int = 8,
) -> None:
    x, y = pos
    # Draw stroke by offsetting the text in all directions
    for dx in range(-stroke_width, stroke_width + 1, 2):
        for dy in range(-stroke_width, stroke_width + 1, 2):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, font=font, fill=stroke_fill)
    draw.text((x, y), text, font=font, fill=fill)


def generate_thumbnail(
    clip,
    title: str,
    output_path: str,
    subtitle: str = "",
    title_color: Tuple[int, int, int] = (255, 255, 0),   # yellow
    subtitle_color: Tuple[int, int, int] = (255, 255, 255),
    resolution: Tuple[int, int] = (1280, 720),
) -> str:
    """
    Pick the best frame from *clip*, overlay *title* text MrBeast-style,
    and save the thumbnail to *output_path*.  Returns *output_path*.
    """
    print("  [thumbnail] Finding best frame …")
    frame = pick_best_frame(clip)

    img = Image.fromarray(frame).convert("RGB")
    img = img.resize(resolution, Image.LANCZOS)
    w, h = img.size

    # Dark gradient overlay at the bottom for text readability
    gradient = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_grad = ImageDraw.Draw(gradient)
    for y in range(h // 2, h):
        alpha = int(180 * ((y - h // 2) / (h // 2)))
        draw_grad.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), gradient).convert("RGB")

    draw = ImageDraw.Draw(img)

    # Try to load a bold font; fall back to default
    font_size_title = int(h * 0.14)
    font_size_sub = int(h * 0.065)

    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size_title)
        font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size_sub)
    except OSError:
        font_title = ImageFont.load_default()
        font_sub = font_title

    # Wrap and draw title
    title_upper = title.upper()
    lines = _wrap_text(title_upper, font_title, int(w * 0.9))

    total_title_h = len(lines) * (font_size_title + 10)
    sub_h = font_size_sub + 10 if subtitle else 0
    total_h = total_title_h + sub_h

    y_start = h - total_h - 60

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_title)
        lw = bbox[2] - bbox[0]
        x = (w - lw) // 2
        _draw_text_with_stroke(draw, (x, y_start), line, font_title, fill=title_color, stroke_width=10)
        y_start += font_size_title + 10

    # Draw subtitle
    if subtitle:
        bbox = draw.textbbox((0, 0), subtitle, font=font_sub)
        sw = bbox[2] - bbox[0]
        x = (w - sw) // 2
        _draw_text_with_stroke(draw, (x, y_start + 5), subtitle, font_sub, fill=subtitle_color, stroke_width=6)

    img.save(output_path, "JPEG", quality=95)
    print(f"  [thumbnail] Saved → {output_path}")
    return output_path
