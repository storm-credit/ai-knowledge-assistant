import hashlib

import feedparser
from typing import List
from .config import Source
from .models import Item

def parse_feed(source_or_xml, src: Source) -> List[Item]:
    """source_or_xml: RSS XML 문자열 또는 URL (feedparser가 둘 다 처리)."""
    parsed = feedparser.parse(source_or_xml)
    items: List[Item] = []
    for e in parsed.entries:
        item_id = getattr(e, "id", None) or getattr(e, "link", "") or e.get("title", "")
        if not item_id:
            # id·link·title 전부 없으면 빈 id로 dedup이 오염됨 → 해시 대체 id
            material = f"{e.get('title', '')}{e.get('published', '')}"
            if not material.strip():
                print(f"[warn] {src.name}: id·link·제목·날짜가 모두 없는 엔트리 skip")
                continue
            item_id = "sha1:" + hashlib.sha1(material.encode("utf-8")).hexdigest()
        items.append(Item(
            source_name=src.name,
            source_type=src.type,
            id=item_id,
            title=e.get("title", "(제목 없음)"),
            link=e.get("link", ""),
            published=e.get("published", ""),
            raw_text=e.get("summary", "") or e.get("description", ""),
        ))
    return items

def fetch_feed(src: Source) -> List[Item]:
    return parse_feed(src.rss, src)
