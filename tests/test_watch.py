"""모델 doc 변경 감시기 (docs/15) — 구조 테스트 (fetch·LLM 주입)."""
import os

import pytest

from collector.watch import (WATCH_PROMPT, _html_to_text, diff_text,
                             load_providers, run_watch, slug_for)


# ── HTML → 텍스트 ─────────────────────────────────────────────────────────

def test_html_to_text_strips_tags_and_scripts():
    html = ("<html><head><style>.x{color:red}</style></head>"
            "<body><script>alert(1)</script><h1>제목</h1>"
            "<p>본문   내용</p></body></html>")
    t = _html_to_text(html)
    assert "제목" in t and "본문 내용" in t
    assert "alert" not in t and "color:red" not in t
    assert "<" not in t


def test_html_to_text_normalizes_whitespace():
    assert _html_to_text("a\n\n\n  b\t\tc") == "a b c"


# ── diff ─────────────────────────────────────────────────────────────────

def test_diff_text_no_change_returns_empty():
    assert diff_text("같은 내용\n둘째 줄", "같은 내용\n둘째 줄") == ""


def test_diff_text_shows_added_lines():
    d = diff_text("한 줄", "한 줄\n새 모델 출시")
    assert "새 모델 출시" in d
    assert d.lstrip().startswith("+") or "\n+" in d


def test_slug_for_is_filesystem_safe():
    s = slug_for("Gemini", "https://ai.google.dev/gemini-api/docs/changelog")
    assert "/" not in s and ":" not in s
    assert s.startswith("Gemini")


# ── 설정 로드 ────────────────────────────────────────────────────────────

def test_load_providers(tmp_path):
    (tmp_path / "model_docs.yaml").write_text(
        "providers:\n  - name: Gemini\n    url: http://x/cl\n", encoding="utf-8")
    ps = load_providers(str(tmp_path / "model_docs.yaml"))
    assert ps == [{"name": "Gemini", "url": "http://x/cl"}]


# ── run_watch 오케스트레이션 ──────────────────────────────────────────────

class FakeResp:
    def __init__(self, c): self.choices = [type("C", (), {"message": type("M", (), {"content": c})})]


class FakeLLM:
    def __init__(self, c): self._c = c; self.n = 0; self.chat = type("Ch", (), {"completions": self})()
    def create(self, **k): self.n += 1; return FakeResp(self._c)


def _env(tmp_path, providers):
    (tmp_path / "model_docs.yaml").write_text(
        "providers:\n" + "".join(
            f"  - name: {p}\n    url: http://x/{p}\n" for p in providers),
        encoding="utf-8")
    return dict(config=str(tmp_path / "model_docs.yaml"),
                snap_dir=str(tmp_path / "snap"),
                out_dir=str(tmp_path / "model-updates"),
                min_len=1)   # 테스트 콘텐츠는 짧으므로 SPA 방어 임계 낮춤


def test_first_run_stores_baseline_no_llm(tmp_path):
    env = _env(tmp_path, ["Gemini"])
    llm = FakeLLM("- 변경 요약")
    path = run_watch(date="2026-07-11", fetch=lambda u: "<p>초기 내용</p>",
                     client=llm, **env)
    assert llm.n == 0                    # 첫 실행은 요약 안 함
    assert path is None                  # 노트 없음
    assert os.listdir(env["snap_dir"])   # baseline 스냅샷 저장됨


def test_change_summarizes_and_writes_note_then_updates_snapshot(tmp_path):
    env = _env(tmp_path, ["Gemini"])
    llm = FakeLLM("- Gemini 3.0 출시 (영향)")
    # 1) baseline
    run_watch(date="2026-07-10", fetch=lambda u: "<p>구버전</p>", client=llm, **env)
    # 2) 변경 발생
    path = run_watch(date="2026-07-11", fetch=lambda u: "<p>구버전 그리고 신규 항목</p>",
                     client=llm, **env)
    assert llm.n == 1
    assert path is not None
    text = open(path, encoding="utf-8").read()
    assert "2026-07-11" in text
    assert "## Gemini" in text
    assert "Gemini 3.0 출시" in text


def test_no_change_no_llm_no_note(tmp_path):
    env = _env(tmp_path, ["Gemini"])
    llm = FakeLLM("- x")
    run_watch(date="2026-07-10", fetch=lambda u: "<p>동일</p>", client=llm, **env)
    path = run_watch(date="2026-07-11", fetch=lambda u: "<p>동일</p>", client=llm, **env)
    assert llm.n == 0 and path is None


class BoomLLM:
    """create()가 항상 예외를 던지는 페이크."""
    def __init__(self): self.chat = type("Ch", (), {"completions": self})()
    def create(self, **k): raise RuntimeError("LLM down")


def test_summary_failure_keeps_old_snapshot_for_retry(tmp_path):
    env = _env(tmp_path, ["Gemini"])
    run_watch(date="2026-07-10", fetch=lambda u: "<p>old baseline text</p>",
              client=FakeLLM("x"), **env)
    snap = os.path.join(env["snap_dir"], os.listdir(env["snap_dir"])[0])
    before = open(snap, encoding="utf-8").read()

    run_watch(date="2026-07-11", fetch=lambda u: "<p>old baseline text and new stuff</p>",
              client=BoomLLM(), **env)
    assert open(snap, encoding="utf-8").read() == before   # 스냅샷 미갱신 → 다음에 재시도


def test_fetch_failure_isolated(tmp_path):
    env = _env(tmp_path, ["Gemini", "OpenAI"])
    llm = FakeLLM("- 변경")
    def fetch(u):
        if u.endswith("Gemini"):
            raise RuntimeError("network")
        return "<p>초기</p>"
    # 한 소스 실패가 다른 소스 처리를 막지 않음 (예외 전파 안 함)
    run_watch(date="2026-07-11", fetch=fetch, client=llm, **env)
    snaps = os.listdir(env["snap_dir"])
    assert any("OpenAI" in s for s in snaps)   # OpenAI는 baseline 저장됨


def test_short_page_skipped(tmp_path):
    env = _env(tmp_path, ["Gemini"])
    env["min_len"] = 200
    run_watch(date="2026-07-11", fetch=lambda u: "짧음", client=FakeLLM("x"), **env)
    assert not os.path.exists(env["snap_dir"]) or not os.listdir(env["snap_dir"])
