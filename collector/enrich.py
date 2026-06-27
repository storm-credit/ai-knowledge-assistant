import re
from typing import Callable, Optional
from .models import Item

def _video_id(url: str) -> Optional[str]:
    m = re.search(r"[?&]v=([\w-]+)", url)
    return m.group(1) if m else None

def _default_fetch_transcript(video_id: str) -> str:
    from youtube_transcript_api import YouTubeTranscriptApi
    parts = YouTubeTranscriptApi.get_transcript(video_id, languages=["ko", "en"])
    return " ".join(p["text"] for p in parts)

def enrich_youtube(item: Item, fetch_transcript: Callable[[str], str] = _default_fetch_transcript) -> Item:
    vid = _video_id(item.link)
    if not vid:
        return item
    try:
        text = fetch_transcript(vid)
        if text.strip():
            item.raw_text = text
    except Exception:
        pass  # 자막 없거나 실패 → 기존 설명 유지 (폴백)
    return item
