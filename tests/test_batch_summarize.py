"""batch_summarize — 여러 항목을 한 콜로 요약 (뉴스 4건/콜, 학습 2건/콜)."""
import json
import re

import pytest

from collector.config import SourcesConfig, Source
from collector.llm import QuotaExhausted
from collector.models import Item
from collector.pipeline import run
from collector.state import StateStore
from collector.store import load_items
from collector.summarize import batch_summarize
import collector.llm as llm_mod

CATS = ["개발·학습", "AI 모델·기술", "기타"]


class FakeResp:
    def __init__(self, c):
        self.choices = [type("C", (), {"message": type("M", (), {"content": c})})]


class BatchFakeClient:
    """배치 프롬프트의 [n] 번호를 읽어 항목 전부에 유효한 JSON을 돌려주는 페이크.

    responses에 콜별 응답을 넣으면 순서대로 소진하고, 다 쓰면 자동 응답으로 전환."""

    def __init__(self, responses=None):
        self.calls = 0
        self.prompts = []
        self.responses = list(responses or [])
        self.chat = type("Ch", (), {"completions": self})()

    def create(self, **k):
        self.calls += 1
        prompt = k["messages"][0]["content"]
        self.prompts.append(prompt)
        if self.responses:
            r = self.responses.pop(0)
            if isinstance(r, Exception):
                raise r
            return FakeResp(r)
        ns = re.findall(r"^\[(\d+)\]", prompt, re.M)
        if ns:   # 배치 프롬프트 → 번호별 JSON 배열
            entries = [{"n": int(n), "summary": f"- 배치요약 {n}",
                        "categories": ["AI 모델·기술"]} for n in ns]
            return FakeResp(json.dumps(entries, ensure_ascii=False))
        return FakeResp("- 단건요약\n카테고리: AI 모델·기술")   # 단건 폴백 프롬프트


def _item(n, learning=False, raw="원문 내용"):
    return Item(source_name="출처", source_type="newsletter", id=f"id{n}",
                title=f"제목{n}", link=f"l{n}", published="", raw_text=raw,
                learning=learning)


def test_four_news_items_in_one_call():
    fake = BatchFakeClient()
    items = [_item(i) for i in range(4)]
    done = batch_summarize(items, client=fake, categories=CATS)
    assert fake.calls == 1
    assert len(done) == 4
    assert all("배치요약" in it.summary for it in done)
    assert all(it.categories == ["AI 모델·기술"] for it in done)


def test_grouping_news_4_learning_2_per_call():
    # 뉴스 5건 → 2콜(4+1), 학습 3건 → 2콜(2+1)
    fake = BatchFakeClient()
    items = [_item(i) for i in range(5)] + [_item(10 + i, learning=True) for i in range(3)]
    done = batch_summarize(items, client=fake, categories=CATS)
    assert fake.calls == 4
    assert len(done) == 8
    assert [it.id for it in done] == [it.id for it in items]   # 입력 순서 유지


def test_batch_prompts_keep_single_prompt_rules():
    fake = BatchFakeClient()
    batch_summarize([_item(1), _item(2, learning=True)], client=fake, categories=CATS)
    news_p = next(p for p in fake.prompts if "핵심 포인트" in p)
    learn_p = next(p for p in fake.prompts if "학습 카드" in p)
    for p in (news_p, learn_p):
        assert "지어내" in p                    # 지어내기 금지
        assert "개발·학습" in p                 # 카테고리 목록 포함
        assert '"n"' in p                       # 번호 키 JSON 배열 요구
    assert "핵심 개념" in learn_p and "쿠폰" in learn_p and "헤딩" in learn_p


def test_batch_raw_text_capped_at_3000():
    fake = BatchFakeClient()
    batch_summarize([_item(1, raw="a" * 5000)], client=fake, categories=CATS)
    assert "a" * 3000 in fake.prompts[0]
    assert "a" * 3001 not in fake.prompts[0]


def test_code_fenced_json_response_is_parsed():
    body = json.dumps([{"n": 1, "summary": "- ok", "categories": ["기타"]}], ensure_ascii=False)
    fake = BatchFakeClient(responses=[f"```json\n{body}\n```"])
    done = batch_summarize([_item(1)], client=fake, categories=CATS)
    assert fake.calls == 1
    assert done[0].summary == "- ok" and done[0].categories == ["기타"]


def test_missing_number_falls_back_to_single_call_for_that_item_only():
    # 배치 응답에서 n=2 누락 → 그 항목만 단건 폴백 (총 2콜)
    partial = json.dumps([{"n": 1, "summary": "- b1", "categories": ["기타"]},
                          {"n": 3, "summary": "- b3", "categories": ["기타"]}],
                         ensure_ascii=False)
    fake = BatchFakeClient(responses=[partial, "- 단건폴백\n카테고리: 기타"])
    items = [_item(1), _item(2), _item(3)]
    done = batch_summarize(items, client=fake, categories=CATS)
    assert fake.calls == 2
    assert len(done) == 3
    assert items[0].summary == "- b1"
    assert items[1].summary == "- 단건폴백"   # 누락 항목만 단건 콜
    assert items[2].summary == "- b3"


def test_whole_json_broken_falls_back_per_item():
    fake = BatchFakeClient(responses=["JSON 아님 그냥 텍스트"])
    items = [_item(1), _item(2), _item(3)]
    done = batch_summarize(items, client=fake, categories=CATS)
    assert fake.calls == 4               # 배치 1콜 + 단건 폴백 3콜
    assert len(done) == 3
    assert all("단건요약" in it.summary for it in items)


def test_learning_item_without_category_defaults_to_dev():
    body = json.dumps([{"n": 1, "summary": "**핵심 개념**\n- a", "categories": []}],
                      ensure_ascii=False)
    fake = BatchFakeClient(responses=[body])
    done = batch_summarize([_item(1, learning=True)], client=fake, categories=CATS)
    assert done[0].categories == ["개발·학습"]


def test_quota_exhausted_propagates():
    class Boom:
        def __init__(self):
            self.chat = type("Ch", (), {"completions": self})()

        def create(self, **k):
            raise RuntimeError("429 quota exceeded")

    with pytest.raises(QuotaExhausted):
        batch_summarize([_item(1)], client=Boom(), categories=CATS)


def test_throttle_sleep_once_per_batch_call():
    fake = BatchFakeClient()
    slept = {"n": 0}
    items = [_item(i) for i in range(5)]   # 뉴스 5건 → 2콜
    batch_summarize(items, client=fake, categories=CATS,
                    sleep=lambda *_: slept.__setitem__("n", slept["n"] + 1),
                    throttle_seconds=5.0)
    assert slept["n"] == fake.calls == 2


# ── pipeline 통합 ──────────────────────────────────────────────

def _worst_day_cfg():
    """최악의 날 시나리오: 뉴스 8피드 + 학습 3피드, 피드당 5건."""
    news = [Source(name=f"뉴스{i}", rss="x", type="newsletter") for i in range(8)]
    learn = [Source(name=f"학습{i}", rss="x", type="youtube", learning=True)
             for i in range(3)]
    return SourcesConfig(youtube=learn, newsletters=news)


def _fetch5(src):
    return [Item(source_name=src.name, source_type=src.type,
                 id=f"{src.name}-{i}", title=f"{src.name} 글{i}", link="l",
                 published="", raw_text="원문") for i in range(5)]


def test_pipeline_worst_day_fits_in_18_call_budget(tmp_path, monkeypatch):
    # 11피드 × 5건 = 뉴스 40건(10콜) + 학습 15건(8콜) = 18콜 ≤ 예산 18
    fake = BatchFakeClient()
    monkeypatch.setattr(llm_mod, "_default_clients", lambda: [fake])
    monkeypatch.setattr(llm_mod, "_default_budget",
                        llm_mod.CallBudget(str(tmp_path / "budget.json"), limit=18))
    monkeypatch.setattr(llm_mod, "_default_breaker", llm_mod.CircuitBreaker())
    state = StateStore(str(tmp_path / "seen.json"))
    store_path = str(tmp_path / "items.jsonl")

    # summarize 미주입 → 실제 cron 경로(배치) 사용
    run(_worst_day_cfg(), state, out_dir=str(tmp_path / "out"), date="2026-07-02",
        fetch=_fetch5, enrich=lambda i: i, sleep=lambda *_: None,
        items_store=store_path)

    assert fake.calls <= 18
    assert fake.calls == 18   # 뉴스 40/4=10 + 학습 15/2=8
    saved = load_items(store_path)
    assert len(saved) == 55
    assert all(not state.is_new(it.id) for it in saved)


def test_pipeline_batch_quota_midway_keeps_done_and_retries_rest(tmp_path, monkeypatch):
    # 첫 배치 콜 성공 후 429 → 성공분만 seen, 나머지는 재시도 가능
    ok_body = json.dumps([{"n": i, "summary": f"- s{i}", "categories": ["기타"]}
                          for i in range(1, 5)], ensure_ascii=False)
    fake = BatchFakeClient(responses=[ok_body, RuntimeError("429 quota exceeded")])
    monkeypatch.setattr(llm_mod, "_default_clients", lambda: [fake])
    monkeypatch.setattr(llm_mod, "_default_budget",
                        llm_mod.CallBudget(str(tmp_path / "budget.json"), limit=18))
    monkeypatch.setattr(llm_mod, "_default_breaker", llm_mod.CircuitBreaker())
    cfg = SourcesConfig(youtube=[], newsletters=[
        Source(name="뉴스", rss="x", type="newsletter")])
    state = StateStore(str(tmp_path / "seen.json"))

    def fetch8(src):
        return [Item(source_name=src.name, source_type=src.type, id=f"n{i}",
                     title=f"글{i}", link="l", published="", raw_text="원문")
                for i in range(8)]

    run(cfg, state, out_dir=str(tmp_path / "out"), date="2026-07-02",
        fetch=fetch8, enrich=lambda i: i, sleep=lambda *_: None,
        limit_per_feed=8, items_store=str(tmp_path / "items.jsonl"))

    for i in range(4):
        assert state.is_new(f"n{i}") is False    # 첫 그룹 4건 성공 → seen
    for i in range(4, 8):
        assert state.is_new(f"n{i}") is True     # 나머지는 다음 실행 때 재시도


def test_pipeline_injected_summarize_keeps_per_item_path(tmp_path):
    # summarize 주입 시 기존 계약(항목당 1콜) 유지
    cfg = SourcesConfig(youtube=[], newsletters=[
        Source(name="뉴스", rss="x", type="newsletter")])
    state = StateStore(str(tmp_path / "seen.json"))
    calls = {"n": 0}

    def fake_sum(it):
        calls["n"] += 1
        it.summary = "요약"
        return it

    run(cfg, state, out_dir=str(tmp_path / "out"), date="2026-07-02",
        fetch=lambda src: [_item(1), _item(2)], enrich=lambda i: i,
        summarize=fake_sum, sleep=lambda *_: None,
        items_store=str(tmp_path / "items.jsonl"))

    assert calls["n"] == 2   # 항목당 1콜
