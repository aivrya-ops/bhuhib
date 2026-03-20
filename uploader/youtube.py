"""
YouTube uploader using the YouTube Data API v3.

Setup:
  1. Go to https://console.cloud.google.com/
  2. Create a project → enable "YouTube Data API v3"
  3. Create OAuth 2.0 credentials (Desktop app)
  4. Download the JSON and save it as credentials/youtube_client_secrets.json
"""
from __future__ import annotations

import os
import pickle

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_CACHE = "credentials/youtube_token.pickle"


def _get_authenticated_service(client_secrets_file: str):
    creds = None

    if os.path.exists(TOKEN_CACHE):
        with open(TOKEN_CACHE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
            creds = flow.run_local_server(port=0)
        os.makedirs("credentials", exist_ok=True)
        with open(TOKEN_CACHE, "wb") as f:
            pickle.dump(creds, f)

    return build("youtube", "v3", credentials=creds)


def upload(
    video_path: str,
    client_secrets_file: str,
    title: str = "",
    description: str = "",
    tags: list[str] | None = None,
    privacy: str = "private",
) -> str:
    """Upload *video_path* to YouTube. Returns the video URL."""
    if not title:
        title = os.path.splitext(os.path.basename(video_path))[0]

    youtube = _get_authenticated_service(client_secrets_file)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": "22",  # People & Blogs
        },
        "status": {"privacyStatus": privacy},
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part=",".join(body.keys()), body=body, media_body=media)

    print("  [youtube] Uploading …")
    response = None
    while response is None:
        _, response = request.next_chunk()

    video_id = response["id"]
    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"  [youtube] Uploaded: {url}")
    return url
