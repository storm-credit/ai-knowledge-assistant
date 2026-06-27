from collector.config import Source
from collector.feeds import parse_feed

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>새 글 제목</title>
    <link>https://example.com/a</link>
    <guid>guid-a</guid>
    <pubDate>Fri, 27 Jun 2026 00:00:00 +0000</pubDate>
    <description>본문 설명입니다</description>
  </item>
</channel></rss>"""

def test_parse_feed_maps_entries_to_items():
    src = Source(name="SaaStr", rss="x", type="newsletter")
    items = parse_feed(RSS, src)
    assert len(items) == 1
    it = items[0]
    assert it.title == "새 글 제목"
    assert it.id == "guid-a"
    assert it.source_name == "SaaStr"
    assert "본문 설명" in it.raw_text
