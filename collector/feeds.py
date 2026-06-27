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
