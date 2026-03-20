"""
Instagram uploader using the Instagram Graph API (Reels / video posts).

Setup:
  1. You need a Facebook Developer account and a connected Instagram Business
     or Creator account.
  2. Create a Facebook App → add Instagram Graph API product.
  3. Generate a long-lived User Access Token with instagram_basic,
     instagram_content_publish, and pages_read_engagement permissions.
  4. Fill in access_token and ig_user_id in config.yaml.

Docs: https://developers.facebook.com/docs/instagram-api/guides/content-publishing
"""
from __future__ import annotations

import os
import time

import requests

GRAPH_BASE = "https://graph.facebook.com/v18.0"


def _create_container(ig_user_id: str, video_url: str, caption: str, access_token: str) -> str:
    """Step 1: Create a media container and return its container_id."""
    url = f"{GRAPH_BASE}/{ig_user_id}/media"
    params = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": access_token,
    }
    resp = requests.post(url, params=params)
    resp.raise_for_status()
    return resp.json()["id"]


def _publish_container(ig_user_id: str, container_id: str, access_token: str) -> str:
    """Step 2: Publish the container and return the media_id."""
    url = f"{GRAPH_BASE}/{ig_user_id}/media_publish"
    params = {
        "creation_id": container_id,
        "access_token": access_token,
    }
    resp = requests.post(url, params=params)
    resp.raise_for_status()
    return resp.json()["id"]


def upload(
    video_url: str,
    access_token: str,
    ig_user_id: str,
    caption: str = "",
) -> str:
    """
    Publish a video Reel to Instagram.

    *video_url* must be a publicly accessible URL (Instagram fetches it).
    Tip: upload your rendered file to a cloud storage bucket first,
         then pass the public URL here.

    Returns the Instagram media_id.
    """
    if not access_token or not ig_user_id:
        raise ValueError("Instagram access_token and ig_user_id must be set in config.yaml")

    print("  [instagram] Creating media container …")
    container_id = _create_container(ig_user_id, video_url, caption, access_token)

    # Poll until the container is ready
    status_url = f"{GRAPH_BASE}/{container_id}"
    for _ in range(30):
        time.sleep(5)
        status_resp = requests.get(
            status_url,
            params={"fields": "status_code", "access_token": access_token},
        )
        status_resp.raise_for_status()
        code = status_resp.json().get("status_code")
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise RuntimeError(f"Instagram container failed: {status_resp.json()}")

    print("  [instagram] Publishing …")
    media_id = _publish_container(ig_user_id, container_id, access_token)
    print(f"  [instagram] Published! media_id={media_id}")
    return media_id
