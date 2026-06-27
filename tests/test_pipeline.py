from collector.config import SourcesConfig, Source
from collector.models import Item
from collector.state import StateStore
from collector.pipeline import run

def test_run_skips_seen_and_writes_only_new(tmp_path):
    cfg = SourcesConfig(
        youtube=[Source(name="조코딩", rss="x", type="youtube")],
        newsletters=[])
    state = StateStore(str(tmp_path / "seen.json"))
    state.mark_seen("old")  # 이미 본 항목

    def fake_fetch(src):
        return [Item(source_name=src.name, source_type=src.type, id="old",
                     title="이전", link="l", published=""),
                Item(source_name=src.name, source_type=src.type, id="new",
                     title="신규", link="l2", published="", raw_text="원문")]

    def fake_summarize(item):
        item.summary = "요약:" + item.title
        return item

    path = run(cfg, state, out_dir=str(tmp_path / "out"), date="2026-06-27",
               fetch=fake_fetch, summarize=fake_summarize, enrich=lambda i: i)

    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "신규" in content and "이전" not in content   # 새 것만
    assert state.is_new("new") is False                   # 이제 본 것으로 기록
