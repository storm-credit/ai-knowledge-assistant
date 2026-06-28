# 위키 v2.0 (내용 강화) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** 토픽 페이지에서 클릭 없이 각 소식의 실제 내용(핵심 포인트 5~7개)이 보이게 한다.

**Architecture:** 두 군데만 바꾼다 — (1) 요약 프롬프트를 3줄→불릿 5~7개로(앞으로 수집분), (2) `render_page`가 각 항목 아래에 저장된 요약을 표시(기존 데이터에도 즉시 적용, LLM 불필요). 마지막에 `wiki` 재실행으로 기존 페이지를 새 형식으로 다시 렌더.

**Tech Stack:** 기존 Python collector, pytest. LLM 호출 추가 없음(프롬프트는 토큰만↑, 렌더는 호출 0).

---

## Task 1: 요약 프롬프트 강화 (불릿 5~7개)

**Files:** Modify `collector/summarize.py`, Test `tests/test_summarize_classify.py`

- [ ] **Step 1: 실패 테스트 추가** — `tests/test_summarize_classify.py`에 추가:
```python
def test_combined_keeps_multiline_bullet_summary():
    from collector.models import Item
    from collector.summarize import summarize_and_classify
    class R:
        def __init__(s,c): s.choices=[type("C",(),{"message":type("M",(),{"content":c})})]
    class FC:
        def __init__(s,c): s._c=c; s.chat=type("Ch",(),{"completions":s})()
        def create(s,**k): return R(s._c)
    it = Item(source_name="노정석", source_type="youtube", id="x",
              title="EP100", link="l", published="2026-06-27", raw_text="원문")
    fake = FC("- 포인트 하나\n- 포인트 둘\n- 포인트 셋\n카테고리: AI 모델·기술")
    out = summarize_and_classify(it, client=fake)
    assert "포인트 하나" in out.summary and "포인트 셋" in out.summary
    assert "카테고리" not in out.summary          # 카테고리 줄은 요약서 제외
    assert out.categories == ["AI 모델·기술"]
```

- [ ] **Step 2: 실패 확인** — `.venv/Scripts/python -m pytest tests/test_summarize_classify.py -v` → 통과/실패 확인 (현 파서로도 통과할 수 있음; 통과하면 그대로 두고 프롬프트만 강화)

- [ ] **Step 3: 프롬프트 강화** — `collector/summarize.py`에서 `SUMMARIZE_CLASSIFY_PROMPT`를 교체:
```python
SUMMARIZE_CLASSIFY_PROMPT = (
    "다음 콘텐츠를 한국어로 핵심 포인트 5~7개로 자세히 요약하라. "
    "각 포인트는 '- '로 시작하는 불릿 한 줄로, 구체적 사실·수치·맥락을 담아라(단순 한 줄 요약 금지). "
    "원문에 있는 내용만 사용하고, 없는 사실은 절대 지어내지 마라. "
    "그 다음 마지막 줄에 '카테고리: '로 시작해 아래 목록 중 가장 맞는 것 1개(최대 2개)만 쉼표로 적어라. "
    "목록에 없으면 '기타'.\n\n"
    "카테고리 목록: {categories}\n\n"
    "제목: {title}\n출처: {source}\n내용:\n{body}"
)
```
그리고 `PROMPT`(summarize_item용)도 일관되게 교체:
```python
PROMPT = (
    "다음 콘텐츠를 한국어로 핵심 포인트 5~7개 불릿('- '로 시작)으로 자세히 요약하라. "
    "원문에 있는 내용만 사용하고, 없는 사실은 절대 지어내지 마라. "
    "마지막 줄에 관련 주제 태그를 #해시태그 3개 이하로 붙여라.\n\n"
    "제목: {title}\n출처: {source}\n내용:\n{body}"
)
```

- [ ] **Step 4: 통과 확인** — `pytest tests/test_summarize_classify.py -v` → PASS
- [ ] **Step 5: 커밋** — `git add collector/summarize.py tests/test_summarize_classify.py && git commit -m "feat(wiki): richer 5-7 bullet summaries in combined prompt"`

---

## Task 2: 토픽 페이지에 요약 표시

**Files:** Modify `collector/topics.py` (`render_page`), Test `tests/test_topics_render.py`

- [ ] **Step 1: 실패 테스트** — `tests/test_topics_render.py`의 `test_render_and_write`에 요약 표시 검증 추가 (기존 테스트 수정):
```python
def test_render_and_write(tmp_path):
    from collector.models import Item
    from collector.topics import TopicStore, render_page, write_pages
    s = TopicStore(str(tmp_path/"topics.json"))
    s.add_item("AI 에이전트", Item(source_name="조코딩", source_type="x", id="a",
               title="글a", link="http://a", published="2026-06-27",
               summary="- 핵심 포인트 A\n- 핵심 포인트 B"))
    s.set_overview("AI 에이전트", "이 주제 개요입니다", ["Claude"])
    md = render_page("AI 에이전트", s.data["AI 에이전트"])
    assert "## 개요" in md and "이 주제 개요입니다" in md
    assert "### [글a](http://a)" in md            # 항목 제목(링크)
    assert "조코딩" in md                          # 출처/날짜
    assert "핵심 포인트 A" in md and "핵심 포인트 B" in md   # 요약 내용 표시
    assert "[[Claude]]" in md
    paths = write_pages(s, str(tmp_path/"topics"))
    assert any(p.endswith("AI 에이전트.md") for p in paths)
```

- [ ] **Step 2: 실패 확인** — `pytest tests/test_topics_render.py -v` → FAIL (요약 내용 "핵심 포인트 A" 미표시)

- [ ] **Step 3: 구현** — `collector/topics.py`의 `render_page`를 교체:
```python
def render_page(topic: str, t: dict) -> str:
    lines = [f"# {topic}", "", f"> 📌 {len(t['sources'])}개 출처에서 언급", ""]
    if t.get("overview"):
        lines += ["## 개요", t["overview"], ""]
    lines.append("## 관련 소식")
    lines.append("")
    for it in reversed(t["items"]):   # 최신 먼저
        date = (it.get("date") or "")[:10]
        lines.append(f"### [{it['title']}]({it['link']})")
        lines.append(f"{it['source']} · {date}")
        summ = (it.get("summary") or "").strip()
        if summ:
            lines.append("")
            lines.append(summ)
        lines.append("")
    if t.get("related"):
        lines += ["## 관련 주제", " · ".join(f"[[{r}]]" for r in t["related"]), ""]
    return "\n".join(lines).rstrip() + "\n"
```

- [ ] **Step 4: 통과 확인** — `pytest tests/test_topics_render.py -v` → PASS; 전체 `pytest -q`도 PASS (다른 렌더 의존 테스트 확인)
- [ ] **Step 5: 커밋** — `git add collector/topics.py tests/test_topics_render.py && git commit -m "feat(wiki): show per-item summary content on topic pages"`

---

## Task 3: 기존 페이지 재렌더 + 검증 + 병합

- [ ] **Step 1: 재렌더 (LLM 불필요)** — 모든 항목이 이미 분류돼 있어 `wiki` 재실행은 분류 0건이고 페이지만 새 형식으로 다시 씀:
```bash
cd "C:/ProjectS/ai-knowledge-assistant" && .venv/Scripts/python -m collector wiki
```
Expected: `[wiki] 0건 분류, N개 주제 페이지` (LLM 호출 거의 없음)

- [ ] **Step 2: 검증** — 토픽 페이지에 요약 내용이 보이는지:
```bash
head -25 "notes/topics/AI 모델·기술.md"
```
Expected: 각 `### [제목](링크)` 아래에 출처·날짜 + 요약(불릿/문장)이 보임

- [ ] **Step 3: 커밋 + 푸시**
```bash
git add notes/topics && git commit -m "feat: re-render topic pages with inline summaries"
git push origin master
```

---

## 완료 정의 (v2.0)
- 토픽 페이지를 열면 각 소식의 **요약 내용이 제목 아래 바로** 보인다(클릭 불필요).
- 앞으로 수집되는 항목은 **핵심 포인트 5~7개**로 더 자세히 요약된다.
- 추가 LLM 호출 없이 기존 페이지도 새 형식으로 갱신됨.
