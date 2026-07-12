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


def test_html_to_text_preserves_block_lines():
    # #1 수정: 블록마다 줄바꿈 보존 → 줄 단위 diff가 의미 있어야
    t = _html_to_text("<p>첫 블록</p><p>둘째 블록</p><li>셋째</li>")
    lines = t.splitlines()
    assert "첫 블록" in lines and "둘째 블록" in lines and "셋째" in lines
    assert len(lines) >= 3   # 한 줄로 뭉개지지 않음


def test_html_to_text_collapses_within_line_whitespace():
    # 줄 안의 연속 공백/탭만 하나로, 줄바꿈은 경계로 보존
    assert _html_to_text("<p>a   b\t\tc</p>") == "a b c"


def test_html_to_text_removes_comments():
    # #4: 주석은 통째 제거 (첫 '>'에서 안 끊김)
    t = _html_to_text("<p>본문</p><!-- 광고 > 조각 --><p>끝</p>")
    assert "조각" not in t and "광고" not in t
    assert "본문" in t and "끝" in t


def test_change_diff_is_line_local_not_whole_page():
    # #1 핵심: 한 블록만 바뀌면 그 블록만 diff에 나와야 (전체 페이지 아님)
    old = _html_to_text("<p>공통1</p><p>공통2</p><p>공통3</p>")
    new = _html_to_text("<p>공통1</p><p>신규 모델 출시</p><p>공통2</p><p>공통3</p>")
    d = diff_text(old, new)
    assert "신규 모델 출시" in d
    assert "공통1" not in d and "공통3" not in d   # 안 바뀐 줄은 diff에 없음


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


def test_same_day_rerun_merges_sections(tmp_path):
    # #2: 같은 날 재실행 시 앞서 쓴 provider 섹션이 유실되지 않고 병합돼야
    env = _env(tmp_path, ["Gemini", "OpenAI"])
    llm = FakeLLM("- 변경 요약")
    # baseline 둘 다
    run_watch(date="2026-07-12", fetch=lambda u: "<p>base</p>", client=llm, **env)
    # 아침: Gemini만 변경
    def f1(u): return "<p>base 그리고 Gemini 신규</p>" if u.endswith("Gemini") else "<p>base</p>"
    run_watch(date="2026-07-12", fetch=f1, client=llm, **env)
    # 저녁: OpenAI만 변경 (Gemini는 이제 diff 없음)
    def f2(u): return "<p>base 그리고 Gemini 신규</p>" if u.endswith("Gemini") else "<p>base 그리고 OpenAI 신규</p>"
    path = run_watch(date="2026-07-12", fetch=f2, client=llm, **env)
    text = open(path, encoding="utf-8").read()
    assert "## Gemini" in text and "## OpenAI" in text   # 둘 다 남아야 (덮어쓰기 X)


def test_summarize_change_wraps_diff_in_delimiter():
    # #3: 외부 텍스트 주입 방어 — diff를 구분자로 감싸고 "지시 아님" 명시
    from collector.watch import WATCH_PROMPT
    assert "<diff>" in WATCH_PROMPT and "</diff>" in WATCH_PROMPT
    assert "지시" in WATCH_PROMPT   # delimiter 안은 데이터, 지시가 아니라는 문구


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
