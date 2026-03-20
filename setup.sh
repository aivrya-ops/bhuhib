#!/usr/bin/env bash
# Quick setup script — installs system dependencies and Python packages

set -e

echo "==> Checking for FFmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    echo "==> Installing FFmpeg..."
    sudo apt-get update -qq && sudo apt-get install -y ffmpeg
else
    echo "    FFmpeg already installed."
fi

echo "==> Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "Setup complete! Run your first edit with:"
echo "  python main.py your_video.mp4"
