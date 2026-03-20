#!/usr/bin/env python3
"""
Video Editing Automation
========================
Usage:
    python main.py <video_file> [--config config.yaml] [--no-trim] [--no-captions] [--no-overlay]

Example:
    python main.py my_video.mp4
    python main.py my_video.mp4 --no-trim
    python main.py my_video.mp4 --config my_config.yaml
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile

import yaml
from moviepy.editor import VideoFileClip


# ── helpers ───────────────────────────────────────────────────────────────────

def load_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def export_for_platform(clip: VideoFileClip, out_dir: str, name: str, platform: str, cfg: dict) -> str:
    """Render clip in the resolution required by *platform* and return the output path."""
    pcfg = cfg["output"]["formats"][platform]
    w, h = map(int, pcfg["resolution"].split("x"))
    bitrate = pcfg.get("bitrate", "4000k")

    out_path = os.path.join(out_dir, f"{name}_{platform}.mp4")

    # Resize / crop to target resolution
    clip_w, clip_h = clip.size
    target_ratio = w / h
    src_ratio = clip_w / clip_h

    if abs(src_ratio - target_ratio) < 0.05:
        resized = clip.resize((w, h))
    elif src_ratio > target_ratio:
        # Source is wider — crop sides
        new_w = int(clip_h * target_ratio)
        x1 = (clip_w - new_w) // 2
        resized = clip.crop(x1=x1, width=new_w).resize((w, h))
    else:
        # Source is taller — crop top/bottom
        new_h = int(clip_w / target_ratio)
        y1 = (clip_h - new_h) // 2
        resized = clip.crop(y1=y1, height=new_h).resize((w, h))

    print(f"  [export] Writing {platform} → {out_path}")
    resized.write_videofile(
        out_path,
        bitrate=bitrate,
        audio_codec="aac",
        logger=None,
        verbose=False,
    )
    return out_path


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Automated video editor + uploader")
    parser.add_argument("video", help="Path to the input video file")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--no-trim", action="store_true", help="Skip silence trimming")
    parser.add_argument("--no-captions", action="store_true", help="Skip caption generation")
    parser.add_argument("--no-overlay", action="store_true", help="Skip intro/outro")
    args = parser.parse_args()

    # Validate input
    if not os.path.isfile(args.video):
        print(f"Error: video file not found: {args.video}")
        sys.exit(1)

    cfg = load_config(args.config)
    out_dir = cfg["output"]["directory"]
    os.makedirs(out_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(args.video))[0]

    print(f"\n{'='*55}")
    print(f"  Video Editing Automation")
    print(f"  Input: {args.video}")
    print(f"{'='*55}\n")

    # ── Step 1: Load clip ─────────────────────────────────────────────────────
    print("[1/4] Loading video …")
    clip = VideoFileClip(args.video)
    print(f"      Duration: {clip.duration:.1f}s  |  Resolution: {clip.w}x{clip.h}")

    # ── Step 2: Trim silence ──────────────────────────────────────────────────
    if not args.no_trim and cfg["trimming"]["remove_silence"]:
        print("\n[2/4] Trimming silence …")
        from editor.trimmer import trim_silence
        trim_cfg = cfg["trimming"]
        clip = trim_silence(
            clip,
            silence_thresh_db=trim_cfg["silence_threshold_db"],
            min_silence_ms=trim_cfg["min_silence_ms"],
            padding_ms=trim_cfg["padding_ms"],
        )
        print(f"      After trim: {clip.duration:.1f}s")
    else:
        print("\n[2/4] Silence trimming skipped.")

    # ── Step 3: Add intro / outro ─────────────────────────────────────────────
    intro = cfg.get("intro_clip", "").strip() or None
    outro = cfg.get("outro_clip", "").strip() or None

    if not args.no_overlay and (intro or outro):
        print("\n[3/4] Adding intro/outro …")
        from editor.overlay import add_intro_outro
        clip = add_intro_outro(clip, intro, outro)
        print(f"      After overlay: {clip.duration:.1f}s")
    else:
        print("\n[3/4] Intro/outro skipped.")

    # ── Step 4: Burn captions ─────────────────────────────────────────────────
    if not args.no_captions and cfg["captions"]["enabled"]:
        print("\n[4/4] Generating & burning captions …")
        from editor.captions import burn_captions, CaptionConfig
        cap_cfg = cfg["captions"]
        clip = burn_captions(
            clip,
            CaptionConfig(
                whisper_model=cap_cfg["whisper_model"],
                font=cap_cfg["font"],
                font_size=cap_cfg["font_size"],
                color=cap_cfg["color"],
                position=cap_cfg["position"],
                background=cap_cfg["background"],
            ),
        )
    else:
        print("\n[4/4] Captions skipped.")

    # ── Export per-platform renders ───────────────────────────────────────────
    print("\n[export] Rendering output files …")
    output_paths: dict[str, str] = {}
    formats = cfg["output"]["formats"]

    if any(formats[p]["enabled"] for p in formats):
        for platform, pcfg in formats.items():
            if pcfg["enabled"]:
                path = export_for_platform(clip, out_dir, base_name, platform, cfg)
                output_paths[platform] = path
    else:
        # No specific platform enabled — export a generic file
        generic_path = os.path.join(out_dir, f"{base_name}_edited.mp4")
        print(f"  [export] Writing generic → {generic_path}")
        clip.write_videofile(generic_path, audio_codec="aac", logger=None, verbose=False)
        output_paths["generic"] = generic_path

    clip.close()

    # ── Upload ────────────────────────────────────────────────────────────────
    upload_cfg = cfg.get("upload", {})

    # YouTube
    if "youtube" in output_paths and upload_cfg.get("youtube", {}).get("client_secrets_file"):
        print("\n[upload] YouTube …")
        from uploader.youtube import upload as yt_upload
        yt_cfg = upload_cfg["youtube"]
        yt_upload(
            output_paths["youtube"],
            client_secrets_file=yt_cfg["client_secrets_file"],
            title=yt_cfg.get("title") or base_name,
            description=yt_cfg.get("description", ""),
            tags=yt_cfg.get("tags", []),
            privacy=yt_cfg.get("privacy", "private"),
        )

    # TikTok
    if "tiktok" in output_paths and upload_cfg.get("tiktok", {}).get("access_token"):
        print("\n[upload] TikTok …")
        from uploader.tiktok import upload as tt_upload
        tt_cfg = upload_cfg["tiktok"]
        tt_upload(
            output_paths["tiktok"],
            access_token=tt_cfg["access_token"],
            caption=tt_cfg.get("caption", ""),
            privacy=tt_cfg.get("privacy", "SELF_ONLY"),
        )

    # Instagram — requires a public URL, so we skip auto-upload unless a URL is provided
    # (user must upload to cloud storage first and pass the public URL)

    # ── Done ──────────────────────────────────────────────────────────────────
    print(f"\n{'='*55}")
    print("  Done! Output files:")
    for platform, path in output_paths.items():
        print(f"    [{platform}] {path}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
