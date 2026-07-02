import os
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
               sleep=lambda *_: None, items_store=str(tmp_path / "items.jsonl"))

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
               limit_per_feed=1, sleep=lambda *_: None,
               items_store=str(tmp_path / "items.jsonl"))

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
        sleep=fake_sleep, throttle_seconds=5.0,
        items_store=str(tmp_path / "items.jsonl"))

    assert calls["n"] == 2   # 새 항목 2개만 요약됨 → sleep 2회 (skip 항목 제외)


def test_summarize_failure_keeps_item_retryable(tmp_path):
    cfg = SourcesConfig(
        youtube=[],
        newsletters=[Source(name="SaaStr", rss="x", type="newsletter")])
    state = StateStore(str(tmp_path / "seen.json"))

    def fake_fetch(src):
        return [Item(source_name=src.name, source_type=src.type, id="q1",
                     title="쿼터초과예정", link="l1", published="", raw_text="원문")]

    def boom(item):
        raise RuntimeError("429 quota exceeded")

    path = run(cfg, state, out_dir=str(tmp_path / "out"), date="2026-06-27",
               fetch=fake_fetch, summarize=boom, enrich=lambda i: i,
               sleep=lambda *_: None)

    assert state.is_new("q1") is True          # 실패 항목은 seen 처리 안 됨 → 재시도 가능
    assert not os.path.exists(path)            # 성공 0건 → 다이제스트 안 만듦


def test_quota_exhausted_keeps_item_retryable(tmp_path):
    # QuotaExhausted(예산 소진·서킷브레이커)도 기존 [retry-later] 경로로 처리된다
    from collector.llm import QuotaExhausted
    cfg = SourcesConfig(
        youtube=[],
        newsletters=[Source(name="SaaStr", rss="x", type="newsletter")])
    state = StateStore(str(tmp_path / "seen.json"))

    def fake_fetch(src):
        return [Item(source_name=src.name, source_type=src.type, id="b1",
                     title="예산소진", link="l1", published="", raw_text="원문")]

    def boom(item):
        raise QuotaExhausted("일일 콜 예산 소진 (18/18)")

    path = run(cfg, state, out_dir=str(tmp_path / "out"), date="2026-07-02",
               fetch=fake_fetch, summarize=boom, enrich=lambda i: i,
               sleep=lambda *_: None)

    assert state.is_new("b1") is True          # seen 미표시 → 다음 실행 때 재시도
    assert not os.path.exists(path)


def test_learning_source_flag_propagates_to_item(tmp_path):
    cfg = SourcesConfig(
        youtube=[Source(name="노마드코더", rss="x", type="youtube", learning=True)],
        newsletters=[Source(name="SaaStr", rss="y", type="newsletter")])
    state = StateStore(str(tmp_path / "seen.json"))

    def fake_fetch(src):
        return [Item(source_name=src.name, source_type=src.type, id=src.name,
                     title="t", link="l", published="", raw_text="원문")]

    seen_flags = {}
    def fake_summarize(item):
        seen_flags[item.source_name] = item.learning
        item.summary = "요약"
        return item

    run(cfg, state, out_dir=str(tmp_path / "out"), date="2026-06-27",
        fetch=fake_fetch, summarize=fake_summarize, enrich=lambda i: i,
        sleep=lambda *_: None, items_store=str(tmp_path / "items.jsonl"))

    assert seen_flags["노마드코더"] is True    # 학습형 출처
    assert seen_flags["SaaStr"] is False       # 일반 출처


def test_no_new_items_does_not_overwrite_existing_digest(tmp_path):
    cfg = SourcesConfig(
        youtube=[],
        newsletters=[Source(name="SaaStr", rss="x", type="newsletter")])
    state = StateStore(str(tmp_path / "seen.json"))
    state.mark_seen("a")
    out = tmp_path / "out"
    out.mkdir()
    existing = out / "2026-06-27.md"
    existing.write_text("# 기존 다이제스트\n소중한 내용", encoding="utf-8")

    def fake_fetch(src):
        return [Item(source_name=src.name, source_type=src.type, id="a",
                     title="이미봄", link="l", published="")]

    run(cfg, state, out_dir=str(out), date="2026-06-27",
        fetch=fake_fetch, summarize=lambda i: i, enrich=lambda i: i,
        sleep=lambda *_: None)

    # 0건 재실행이 기존 내용을 덮어쓰지 않음
    assert existing.read_text(encoding="utf-8") == "# 기존 다이제스트\n소중한 내용"
