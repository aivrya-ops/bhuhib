"""
TikTok uploader using the TikTok Content Posting API.

Setup:
  1. Apply for a TikTok Developer account at https://developers.tiktok.com/
  2. Create an app and request the "video.publish" scope
  3. Complete OAuth and paste your access_token in config.yaml

Note: TikTok's Content Posting API requires app approval. During development
      you can only post to your own account using a sandbox token.
"""
from __future__ import annotations

import os
import time

import requests

INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
UPLOAD_URL_FIELD = "upload_url"
PUBLISH_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"


def upload(
    video_path: str,
    access_token: str,
    caption: str = "",
    privacy: str = "SELF_ONLY",
) -> str:
    """Upload *video_path* to TikTok. Returns the publish_id."""
    if not access_token:
        raise ValueError("TikTok access_token is not set in config.yaml")

    file_size = os.path.getsize(video_path)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    # Step 1 — init upload
    init_body = {
        "post_info": {
            "title": caption or os.path.splitext(os.path.basename(video_path))[0],
            "privacy_level": privacy,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": file_size,
            "total_chunk_count": 1,
        },
    }

    print("  [tiktok] Initialising upload …")
    resp = requests.post(INIT_URL, json=init_body, headers=headers)
    resp.raise_for_status()
    data = resp.json()["data"]
    publish_id = data["publish_id"]
    upload_url = data[UPLOAD_URL_FIELD]

    # Step 2 — upload file
    print("  [tiktok] Uploading video bytes …")
    with open(video_path, "rb") as f:
        video_bytes = f.read()

    upload_headers = {
        "Content-Type": "video/mp4",
        "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
        "Content-Length": str(file_size),
    }
    put_resp = requests.put(upload_url, data=video_bytes, headers=upload_headers)
    put_resp.raise_for_status()

    # Step 3 — poll status
    print("  [tiktok] Waiting for processing …")
    for _ in range(20):
        time.sleep(5)
        status_resp = requests.post(
            PUBLISH_URL,
            json={"publish_id": publish_id},
            headers=headers,
        )
        status_resp.raise_for_status()
        status = status_resp.json()["data"]["status"]
        if status == "PUBLISH_COMPLETE":
            print(f"  [tiktok] Published! publish_id={publish_id}")
            return publish_id
        if status in ("FAILED", "PUBLISH_FAILED"):
            raise RuntimeError(f"TikTok upload failed: {status_resp.json()}")

    raise TimeoutError("TikTok upload did not complete in time.")
