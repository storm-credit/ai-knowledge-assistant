import pytest
from collector.config import SourcesConfig, Source
from collector.models import Item
from collector.state import StateStore
from collector.pipeline import run
from collector.store import load_items
import collector.pipeline as pl

def test_run_appends_new_items_to_store(tmp_path):
    cfg = SourcesConfig(youtube=[], newsletters=[Source(name="SaaStr", rss="x", type="newsletter")])
    state = StateStore(str(tmp_path / "seen.json"))
    store_path = str(tmp_path / "items.jsonl")

    def fake_fetch(src):
        return [Item(source_name=src.name, source_type=src.type, id="n1",
                     title="새글", link="l", published="", raw_text="원문")]
    def fake_sum(it): it.summary = "요약"; return it

    run(cfg, state, out_dir=str(tmp_path/"out"), date="2026-06-27",
        fetch=fake_fetch, summarize=fake_sum, enrich=lambda i: i,
        sleep=lambda *_: None, items_store=store_path)

    saved = load_items(store_path)
    assert len(saved) == 1 and saved[0].id == "n1" and saved[0].summary == "요약"


def _cfg():
    return SourcesConfig(youtube=[], newsletters=[Source(name="SaaStr", rss="x", type="newsletter")])

def _fetch_one(src):
    return [Item(source_name=src.name, source_type=src.type, id="n1",
                 title="새글", link="http://l", published="", raw_text="원문")]

def _boom_digest(*a, **k):
    raise RuntimeError("크래시 시뮬레이션")


def test_crash_before_digest_still_persists_summaries(tmp_path, monkeypatch):
    # 요약 성공 후 write_digest 직전 크래시 → items.jsonl과 seen에 성공분 보존 (쿼터 낭비 방지)
    state = StateStore(str(tmp_path / "seen.json"))
    store_path = str(tmp_path / "items.jsonl")
    def fake_sum(it): it.summary = "요약"; return it
    monkeypatch.setattr(pl, "write_digest", _boom_digest)

    with pytest.raises(RuntimeError):
        run(_cfg(), state, out_dir=str(tmp_path / "out"), date="2026-07-02",
            fetch=_fetch_one, summarize=fake_sum, enrich=lambda i: i,
            sleep=lambda *_: None, items_store=store_path)

    saved = load_items(store_path)
    assert len(saved) == 1 and saved[0].summary == "요약"           # 요약 결과 보존
    assert StateStore(str(tmp_path / "seen.json")).is_new("n1") is False   # seen도 디스크에 저장됨


def test_batch_path_persists_before_digest_crash(tmp_path, monkeypatch):
    # 배치 요약 경로(summarize 미주입)도 batch_summarize 반환 직후 영속화된다
    state = StateStore(str(tmp_path / "seen.json"))
    store_path = str(tmp_path / "items.jsonl")
    def fake_batch(items, **k):
        for it in items:
            it.summary = "배치요약"
        return items
    monkeypatch.setattr(pl, "batch_summarize", fake_batch)
    monkeypatch.setattr(pl, "write_digest", _boom_digest)

    with pytest.raises(RuntimeError):
        run(_cfg(), state, out_dir=str(tmp_path / "out"), date="2026-07-02",
            fetch=_fetch_one, enrich=lambda i: i,
            sleep=lambda *_: None, items_store=store_path)

    saved = load_items(store_path)
    assert len(saved) == 1 and saved[0].summary == "배치요약"
    assert StateStore(str(tmp_path / "seen.json")).is_new("n1") is False


def test_rerun_after_crash_no_resummarize_no_dupes(tmp_path, monkeypatch):
    # 크래시 후 재실행: 이미 성공한 항목은 재요약(쿼터 재소비) 없음, 저장 중복 없음
    store_path = str(tmp_path / "items.jsonl")
    seen_path = str(tmp_path / "seen.json")
    calls = {"n": 0}
    def fake_sum(it):
        calls["n"] += 1
        it.summary = "요약"
        return it

    monkeypatch.setattr(pl, "write_digest", _boom_digest)
    with pytest.raises(RuntimeError):
        run(_cfg(), StateStore(seen_path), out_dir=str(tmp_path / "out"), date="2026-07-02",
            fetch=_fetch_one, summarize=fake_sum, enrich=lambda i: i,
            sleep=lambda *_: None, items_store=store_path)
    assert calls["n"] == 1

    monkeypatch.undo()   # 재실행은 정상 write_digest로
    run(_cfg(), StateStore(seen_path), out_dir=str(tmp_path / "out"), date="2026-07-02",
        fetch=_fetch_one, summarize=fake_sum, enrich=lambda i: i,
        sleep=lambda *_: None, items_store=store_path)

    assert calls["n"] == 1                       # 재요약 없음 (seen에 이미 있음)
    assert len(load_items(store_path)) == 1      # 중복 저장 없음
