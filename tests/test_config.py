from collector.config import load_sources

def test_load_sources_parses_youtube_and_newsletters(tmp_path):
    p = tmp_path / "sources.yaml"
    p.write_text(
        "youtube:\n"
        "  - name: 조코딩\n"
        "    channel_id: UC123\n"
        "newsletters:\n"
        "  - name: SaaStr\n"
        "    rss: https://www.saastr.com/feed\n",
        encoding="utf-8")
    cfg = load_sources(str(p))
    assert cfg.youtube[0].name == "조코딩"
    assert cfg.youtube[0].rss == "https://www.youtube.com/feeds/videos.xml?channel_id=UC123"
    assert cfg.newsletters[0].rss == "https://www.saastr.com/feed"
