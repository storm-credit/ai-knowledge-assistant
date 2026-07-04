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


# ── (#17) id·link·title 전부 없는 엔트리의 dedup 오염 방지 ────────────────

RSS_NO_IDS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <pubDate>Fri, 27 Jun 2026 00:00:00 +0000</pubDate>
    <description>본문 A</description>
  </item>
  <item>
    <pubDate>Sat, 28 Jun 2026 00:00:00 +0000</pubDate>
    <description>본문 B</description>
  </item>
</channel></rss>"""

RSS_TOTALLY_EMPTY = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item><description>본문만</description></item>
</channel></rss>"""


def test_empty_id_entries_get_distinct_fallback_ids():
    # id/link/title 없음 → published 기반 sha1 대체 id → 서로 다른 id (dedup 오염 없음)
    src = Source(name="S", rss="x", type="newsletter")
    items = parse_feed(RSS_NO_IDS, src)
    assert len(items) == 2
    assert items[0].id and items[1].id            # 빈 id 없음
    assert items[0].id != items[1].id


def test_entry_without_any_id_material_is_skipped(capsys):
    # title·published까지 전부 없으면 skip + 경고 (같은 빈 id로 뭉개지지 않음)
    src = Source(name="S", rss="x", type="newsletter")
    items = parse_feed(RSS_TOTALLY_EMPTY, src)
    assert items == []
    assert "skip" in capsys.readouterr().out.lower()
