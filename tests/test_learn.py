"""적용형 학습 노트 (docs/14) — 구조 테스트 (FakeClient)."""
import pytest

from collector.learn import (LEARN_PROMPT, MIN_REMAINING, build_prompt,
                             compose_note, find_feed_context, load_profile,
                             note_filename, run_learn)
from collector.llm import CallBudget
from collector.models import Item
from collector.store import append_items


class FakeResp:
    def __init__(self, c): self.choices = [type("C", (), {"message": type("M", (), {"content": c})})]


class FakeClient:
    def __init__(self, c): self._c = c; self.n = 0; self.chat = type("Ch", (), {"completions": self})()
    def create(self, **k): self.n += 1; return FakeResp(self._c)


GOOD_NOTE = ("## 이게 뭔가\n에이전트 실행 틀을 설계하는 일. (불확실)\n\n"
             "## 어떻게 배우나\n- 작은 에이전트 루프부터 만들어본다\n\n"
             "## 내 적용법\n- 수집기 파이프라인에 적용해본다 (제안)\n\n"
             "## 관련\n[[AI 모델·기술]]")


# ── 프로필 ───────────────────────────────────────────────────────────────

def test_load_profile_reads_file(tmp_path):
    p = tmp_path / "me.md"
    p.write_text("파이썬으로 개인 도구를 만든다", encoding="utf-8")
    assert "파이썬" in load_profile(str(p))


def test_load_profile_missing_returns_empty(tmp_path):
    assert load_profile(str(tmp_path / "none.md")) == ""


# ── 프롬프트 ─────────────────────────────────────────────────────────────

def test_build_prompt_includes_concept_profile_context_topics():
    prompt = build_prompt("하네스 엔지니어링", profile="파이썬·PM 성향",
                          context=["- [영상A] 요약..."], topics=["AI 모델·기술"])
    assert "하네스 엔지니어링" in prompt
    assert "파이썬·PM 성향" in prompt
    assert "[영상A]" in prompt
    assert "AI 모델·기술" in prompt
    # grounded/generative 분리 규칙이 프롬프트에 명시돼야
    assert "(불확실)" in prompt
    assert "(제안)" in prompt
    # 오염된 피드 맥락 방어 규칙 (07-03 실전 발견: 광고 섞인 요약이 정의를 오염시킴)
    assert "무시하라" in prompt
    assert "판촉" in prompt


def test_build_prompt_empty_profile_falls_back_to_generic():
    prompt = build_prompt("MCP", profile="", context=[], topics=[])
    assert "(프로필 없음)" in prompt


# ── 노트 합성·파일명 ─────────────────────────────────────────────────────

def test_compose_note_adds_title_and_date():
    note = compose_note("하네스 엔지니어링", GOOD_NOTE, date="2026-07-03")
    assert note.startswith("# 하네스 엔지니어링\n")
    assert "2026-07-03" in note
    assert "## 이게 뭔가" in note


def test_compose_note_strips_model_h1():
    note = compose_note("MCP", "# MCP\n\n" + GOOD_NOTE, date="2026-07-03")
    assert note.count("# MCP\n") == 1   # 모델이 넣은 중복 h1 제거


def test_note_filename_sanitizes_forbidden_chars():
    assert note_filename("A/B: C?") == "A_B_ C_.md"


# ── 피드 맥락 검색 ───────────────────────────────────────────────────────

def _item(id, title, summary=""):
    return Item(source_name="src", source_type="youtube", id=id,
                title=title, link="l", published="2026-07-01", summary=summary)


def test_find_feed_context_matches_title_or_summary(tmp_path):
    store = str(tmp_path / "items.jsonl")
    append_items([_item("a", "하네스 엔지니어링이란"),
                  _item("b", "무관한 글", summary="하네스 얘기 조금"),
                  _item("c", "완전 무관")], store)
    ctx = find_feed_context("하네스", items_store=store)
    assert len(ctx) == 2
    assert any("하네스 엔지니어링이란" in c for c in ctx)


def test_find_feed_context_caps_results(tmp_path):
    store = str(tmp_path / "items.jsonl")
    append_items([_item(f"i{n}", f"하네스 글 {n}") for n in range(10)], store)
    assert len(find_feed_context("하네스", items_store=store, limit=5)) == 5


# ── run_learn (오케스트레이션) ───────────────────────────────────────────

def test_run_learn_writes_note(tmp_path):
    fake = FakeClient(GOOD_NOTE)
    path = run_learn("하네스 엔지니어링", date="2026-07-03", client=fake,
                     items_store=str(tmp_path / "items.jsonl"),
                     topics_path=str(tmp_path / "topics.json"),
                     profile_path=str(tmp_path / "me.md"),
                     out_dir=str(tmp_path / "learn"))
    assert path is not None and fake.n == 1
    text = open(path, encoding="utf-8").read()
    assert text.startswith("# 하네스 엔지니어링")
    for sec in ("## 이게 뭔가", "## 어떻게 배우나", "## 내 적용법", "## 관련"):
        assert sec in text


def test_run_learn_skips_when_budget_low(tmp_path):
    # 잔여 콜이 MIN_REMAINING 미만이면 API를 안 때리고 미룬다 (본업 우선)
    budget = CallBudget(path=str(tmp_path / "b.json"), limit=18,
                        today=lambda: "2026-07-03")
    budget.calls = 18 - MIN_REMAINING + 1   # 잔여 = MIN_REMAINING - 1
    fake = FakeClient(GOOD_NOTE)
    path = run_learn("MCP", date="2026-07-03", client=fake, budget=budget,
                     items_store=str(tmp_path / "i.jsonl"),
                     topics_path=str(tmp_path / "t.json"),
                     profile_path=str(tmp_path / "me.md"),
                     out_dir=str(tmp_path / "learn"))
    assert path is None
    assert fake.n == 0   # API 미호출


def test_run_learn_uses_profile_and_topics(tmp_path):
    (tmp_path / "me.md").write_text("파이썬 자동화 도구 제작", encoding="utf-8")
    (tmp_path / "topics.json").write_text(
        '{"AI 모델·기술": {"items": [], "sources": []}}', encoding="utf-8")
    sent = {}
    class Rec(FakeClient):
        def create(self, **k):
            sent["prompt"] = k["messages"][0]["content"]
            return super().create(**k)
    fake = Rec(GOOD_NOTE)
    run_learn("MCP", date="2026-07-03", client=fake,
              items_store=str(tmp_path / "i.jsonl"),
              topics_path=str(tmp_path / "topics.json"),
              profile_path=str(tmp_path / "me.md"),
              out_dir=str(tmp_path / "learn"))
    assert "파이썬 자동화 도구 제작" in sent["prompt"]
    assert "AI 모델·기술" in sent["prompt"]
