"""학습(learning) 플래그가 config → model로 흐르는지 검증."""
from collector.config import load_sources
from collector.models import Item


def test_item_defaults_to_non_learning():
    it = Item(source_name="s", source_type="youtube", id="x",
              title="t", link="l", published="")
    assert it.learning is False


def test_source_learning_flag_loaded_from_yaml(tmp_path):
    (tmp_path / "sources.yaml").write_text(
        "youtube:\n"
        "  - name: 노마드코더\n"
        "    channel_id: ABC\n"
        "    learning: true\n"
        "  - name: 조코딩\n"
        "    channel_id: DEF\n"
        "newsletters:\n"
        "  - name: The Batch\n"
        "    rss: http://x/feed\n"
        "    learning: true\n"
        "  - name: SaaStr\n"
        "    rss: http://y/feed\n",
        encoding="utf-8")
    cfg = load_sources(str(tmp_path / "sources.yaml"))
    yt = {s.name: s for s in cfg.youtube}
    nl = {s.name: s for s in cfg.newsletters}
    assert yt["노마드코더"].learning is True
    assert yt["조코딩"].learning is False   # 플래그 없으면 기본 False
    assert nl["The Batch"].learning is True
    assert nl["SaaStr"].learning is False
