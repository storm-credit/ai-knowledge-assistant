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
               fetch=fake_fetch, summarize=fake_summarize, enrich=lambda i: i,
               sleep=lambda *_: None)

    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "신규" in content and "이전" not in content   # 새 것만
    assert state.is_new("new") is False                   # 이제 본 것으로 기록


def test_limit_per_feed_only_processes_newest(tmp_path):
    cfg = SourcesConfig(
        youtube=[],
        newsletters=[Source(name="SaaStr", rss="x", type="newsletter")])
    state = StateStore(str(tmp_path / "seen.json"))

    def fake_fetch(src):
        # 최신순(newest first)으로 3개 반환
        return [Item(source_name=src.name, source_type=src.type, id="i1",
                     title="최신", link="l1", published=""),
                Item(source_name=src.name, source_type=src.type, id="i2",
                     title="중간", link="l2", published=""),
                Item(source_name=src.name, source_type=src.type, id="i3",
                     title="오래됨", link="l3", published="")]

    def fake_summarize(item):
        item.summary = "요약:" + item.title
        return item

    path = run(cfg, state, out_dir=str(tmp_path / "out"), date="2026-06-27",
               fetch=fake_fetch, summarize=fake_summarize, enrich=lambda i: i,
               limit_per_feed=1, sleep=lambda *_: None)

    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "최신" in content                       # 가장 최신 1개만
    assert "중간" not in content and "오래됨" not in content
    assert state.is_new("i1") is False             # 처리된 항목만 기록
    assert state.is_new("i2") is True
    assert state.is_new("i3") is True


def test_throttle_sleep_called_once_per_summarized_item(tmp_path):
    cfg = SourcesConfig(
        youtube=[],
        newsletters=[Source(name="SaaStr", rss="x", type="newsletter")])
    state = StateStore(str(tmp_path / "seen.json"))
    state.mark_seen("seen-one")  # 이미 본 항목 → summarize 안 됨

    def fake_fetch(src):
        return [Item(source_name=src.name, source_type=src.type, id="seen-one",
                     title="이미봄", link="l0", published=""),
                Item(source_name=src.name, source_type=src.type, id="n1",
                     title="새1", link="l1", published=""),
                Item(source_name=src.name, source_type=src.type, id="n2",
                     title="새2", link="l2", published="")]

    def fake_summarize(item):
        item.summary = "요약:" + item.title
        return item

    calls = {"n": 0}
    def fake_sleep(_seconds):
        calls["n"] += 1

    run(cfg, state, out_dir=str(tmp_path / "out"), date="2026-06-27",
        fetch=fake_fetch, summarize=fake_summarize, enrich=lambda i: i,
        sleep=fake_sleep, throttle_seconds=5.0)

    assert calls["n"] == 2   # 새 항목 2개만 요약됨 → sleep 2회 (skip 항목 제외)
