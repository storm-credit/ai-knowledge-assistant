# 위키 정리형(테마 묶음) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** 토픽 페이지를 "항목 나열"에서 "테마(소주제)로 묶어 정리된 글"로 바꾼다 — 개요 콜아웃 + 테마별 섹션(정리문 + 항목들) + 짚어둘 단신 + 관련주제.

**Architecture:** 합성 1회 호출이 항목들을 2~4개 테마로 클러스터링해 구조(개요/테마/단신/관련)를 반환 → TopicStore에 themes 저장 → render_page가 테마별로 렌더. LLM은 항목을 **번호로만** 참조(URL은 코드가 렌더, 환각 방지). 호출 수 불변(주제당 1회 재합성).

**Tech Stack:** 기존 Python collector, pytest. 넘버링 하드코딩·인라인 다이어그램 없음(옵시디언 Outline/그래프뷰가 처리).

---

## Task 1: synthesize_structure (테마 클러스터링)

**Files:** Modify `collector/wikisynth.py`, Test `tests/test_wikisynth.py`

- [ ] **Step 1: 실패 테스트 추가**
```python
def test_synthesize_structure_parses_themes_orphans():
    from collector.wikisynth import synthesize_structure
    class R:
        def __init__(s,c): s.choices=[type("C",(),{"message":type("M",(),{"content":c})})]
    class FC:
        def __init__(s,c): s._c=c; s.chat=type("Ch",(),{"completions":s})()
        def create(s,**k): return R(s._c)
    items = [{"title":"A","summary":"a"},{"title":"B","summary":"b"},
             {"title":"C","summary":"c"},{"title":"D","summary":"d"}]
    out = synthesize_structure("AI", items, client=FC(
        "개요: 전체 개요다.\n"
        "[테마] 모델 경쟁 || 경쟁이 치열 || 1,3\n"
        "[테마] 인프라 || 비용이 핵심 || 2\n"
        "[단신] 4\n"
        "관련주제: Claude, GPU"))
    assert out["overview"] == "전체 개요다."
    assert len(out["themes"]) == 2
    assert out["themes"][0]["name"] == "모델 경쟁"
    assert out["themes"][0]["intro"] == "경쟁이 치열"
    assert out["themes"][0]["indexes"] == [1, 3]
    assert out["orphans"] == [4]
    assert out["related"] == ["Claude", "GPU"]
```

- [ ] **Step 2: 실패 확인** — `.venv/Scripts/python -m pytest tests/test_wikisynth.py -v` → FAIL (synthesize_structure 없음)

- [ ] **Step 3: 구현** — `collector/wikisynth.py`에 추가 (기존 synthesize_overview는 남겨둠):
```python
SYNTH_STRUCT_PROMPT = (
    "다음은 '{topic}' 주제로 모인 항목들이다(번호 매김). 한국어로 정리하라.\n"
    "1) '개요: '로 시작해 3~4문장으로 이 분야의 큰 그림.\n"
    "2) 항목들을 2~4개 테마로 묶어라. 각 테마는 한 줄:\n"
    "   '[테마] 테마이름 || 1~2문장 정리 || 항목번호(쉼표)'\n"
    "3) 어느 테마에도 안 맞는 항목: '[단신] 항목번호(쉼표)'\n"
    "4) '관련주제: '로 시작해 관련 주제 2~4개를 쉼표로.\n"
    "원문에 없는 사실은 지어내지 마라. 항목은 번호로만 가리키고 URL은 쓰지 마라.\n\n"
    "항목들:\n{items}"
)

def _nums(s: str):
    out = []
    for tok in s.replace("，", ",").split(","):
        tok = tok.strip()
        if tok.isdigit():
            out.append(int(tok))
    return out

def synthesize_structure(topic: str, items: List[dict], client=None, clients=None,
                         model: str = "gemini-2.5-flash-lite") -> dict:
    numbered = "\n".join(f"[{i+1}] {it.get('title','')} — {it.get('summary','')}"
                         for i, it in enumerate(items))[:8000]
    prompt = SYNTH_STRUCT_PROMPT.format(topic=topic, items=numbered)
    cands = [client] if client is not None else (clients if clients is not None else _default_clients())
    last = None
    for c in cands:
        try:
            resp = c.chat.completions.create(model=model, messages=[{"role":"user","content":prompt}])
            text = resp.choices[0].message.content.strip()
            overview, themes, orphans, related = "", [], [], []
            for line in text.splitlines():
                s = line.strip()
                if s.startswith("개요:"):
                    overview = s[len("개요:"):].strip()
                elif s.startswith("[테마]"):
                    parts = [p.strip() for p in s[len("[테마]"):].split("||")]
                    name = parts[0] if parts else ""
                    intro = parts[1] if len(parts) > 1 else ""
                    idxs = _nums(parts[2]) if len(parts) > 2 else []
                    if name:
                        themes.append({"name": name, "intro": intro, "indexes": idxs})
                elif s.startswith("[단신]"):
                    orphans = _nums(s[len("[단신]"):])
                elif s.startswith("관련주제:"):
                    related = [x.strip().lstrip("#").strip()
                               for x in s[len("관련주제:"):].split(",") if x.strip()]
            return {"overview": overview, "themes": themes[:4],
                    "orphans": orphans, "related": related[:4]}
        except Exception as e:
            last = e
            if _is_quota_error(e):
                continue
            raise
    raise last
```

- [ ] **Step 4: 통과 확인** — `pytest tests/test_wikisynth.py -v` → PASS
- [ ] **Step 5: 커밋** — `git add collector/wikisynth.py tests/test_wikisynth.py && git commit -m "feat(wiki): synthesize_structure clusters items into themes"`

---

## Task 2: TopicStore.set_structure

**Files:** Modify `collector/topics.py`, Test `tests/test_topics_structure.py`

- [ ] **Step 1: 실패 테스트**
```python
from collector.models import Item
from collector.topics import TopicStore

def _mk(i): return Item(source_name="s", source_type="x", id=f"id{i}",
                        title=f"T{i}", link=f"http://{i}", published="2026-06-29", summary=f"s{i}")

def test_set_structure_maps_indexes_to_ids(tmp_path):
    s = TopicStore(str(tmp_path/"t.json"))
    for i in (1,2,3,4): s.add_item("AI", _mk(i))
    s.set_structure("AI", "개요글",
                    themes=[{"name":"테마1","intro":"정리1","indexes":[1,3]}],
                    orphans=[4], related=["Claude"])
    d = s.data["AI"]
    assert d["overview"] == "개요글"
    assert d["themes"][0]["name"] == "테마1"
    assert d["themes"][0]["item_ids"] == ["id1","id3"]   # 번호→id 매핑
    assert d["orphans"] == ["id4"]
    assert d["new_since_synth"] == 0                      # 카운터 리셋
```

- [ ] **Step 2: 실패 확인** — `pytest tests/test_topics_structure.py -v` → FAIL (set_structure 없음)

- [ ] **Step 3: 구현** — `collector/topics.py`의 TopicStore에 메서드 추가(set_overview 아래):
```python
    def set_structure(self, topic: str, overview: str, themes: list,
                      orphans: list, related: list) -> None:
        t = self.data[topic]
        items = t["items"]
        def to_ids(idxs):
            return [items[i-1]["id"] for i in idxs if isinstance(i, int) and 1 <= i <= len(items)]
        t["overview"] = overview
        t["themes"] = [{"name": th["name"], "intro": th.get("intro", ""),
                        "item_ids": to_ids(th.get("indexes", []))} for th in themes]
        t["orphans"] = to_ids(orphans)
        t["related"] = related
        t["new_since_synth"] = 0
```

- [ ] **Step 4: 통과 확인** — `pytest tests/test_topics_structure.py -v` → PASS
- [ ] **Step 5: 커밋** — `git add collector/topics.py tests/test_topics_structure.py && git commit -m "feat(wiki): TopicStore.set_structure (themes + orphans by id)"`

---

## Task 3: render_page 테마별 렌더

**Files:** Modify `collector/topics.py`, Test `tests/test_topics_render.py`

- [ ] **Step 1: 실패 테스트** — `tests/test_topics_render.py`에 추가:
```python
def test_render_themed_page(tmp_path):
    from collector.models import Item
    from collector.topics import TopicStore, render_page
    s = TopicStore(str(tmp_path/"t.json"))
    for i in (1,2): s.add_item("AI", Item(source_name="노정석", source_type="x",
        id=f"id{i}", title=f"글{i}", link=f"http://{i}", published="2026-06-29",
        summary=f"요약{i}"))
    s.set_structure("AI", "전체 개요다",
                    themes=[{"name":"모델 경쟁","intro":"경쟁 치열","indexes":[1]}],
                    orphans=[2], related=["Claude"])
    md = render_page("AI", s.data["AI"])
    assert "> [!abstract] 개요" in md and "전체 개요다" in md
    assert "## 모델 경쟁" in md and "경쟁 치열" in md
    assert "[글1](http://1)" in md and "요약1" in md       # 테마 안 항목+내용
    assert "## 짚어둘 단신" in md and "[글2](http://2)" in md  # 단신
    assert "[[Claude]]" in md
```

- [ ] **Step 2: 실패 확인** — `pytest tests/test_topics_render.py::test_render_themed_page -v` → FAIL

- [ ] **Step 3: 구현** — `collector/topics.py`의 `render_page`를 교체:
```python
def _render_item(lines: list, it: dict) -> None:
    date = (it.get("date") or "")[:10]
    lines.append(f"### [{it['title']}]({it['link']})")
    lines.append(f"{it['source']} · {date}")
    summ = (it.get("summary") or "").strip()
    if summ:
        lines.append("")
        lines.append(summ)
    lines.append("")

def render_page(topic: str, t: dict) -> str:
    lines = [f"# {topic}", "", "> [!abstract] 개요"]
    ov = (t.get("overview") or "").strip()
    for ln in (ov.splitlines() or [""]):
        lines.append(f"> {ln}" if ln else ">")
    lines.append(f"> 📌 {len(t['sources'])}개 출처 · {len(t['items'])}건")
    lines.append("")

    by_id = {it["id"]: it for it in t["items"]}
    themes = t.get("themes") or []
    if themes:
        used = set()
        for th in themes:
            lines.append(f"## {th['name']}")
            if th.get("intro"):
                lines.append(th["intro"]); lines.append("")
            for iid in th.get("item_ids", []):
                it = by_id.get(iid)
                if it:
                    used.add(iid); _render_item(lines, it)
        orphan_ids = t.get("orphans") or []
        orphans = [by_id[i] for i in orphan_ids if i in by_id and i not in used]
        # themes/orphans에서 빠진 항목도 단신으로 흡수
        for iid, it in by_id.items():
            if iid not in used and it not in orphans and iid not in orphan_ids:
                orphans.append(it)
        if orphans:
            lines.append("## 짚어둘 단신")
            for it in orphans:
                date = (it.get("date") or "")[:10]
                lines.append(f"- [{it['title']}]({it['link']}) · {it['source']} · {date}")
            lines.append("")
    else:
        # 테마 없으면 기존 평면 렌더(폴백)
        lines.append("## 관련 소식"); lines.append("")
        for it in reversed(t["items"]):
            _render_item(lines, it)

    if t.get("related"):
        lines += ["## 관련 주제", " · ".join(f"[[{r}]]" for r in t["related"]), ""]
    return "\n".join(lines).rstrip() + "\n"
```

- [ ] **Step 4: 통과 확인** — `pytest tests/test_topics_render.py -v` → PASS. 그리고 전체 `pytest -q` — 기존 `test_render_and_write`가 `## 개요`/`## 관련 소식` 문자열을 검사하면 새 형식(`> [!abstract] 개요`, 테마 없으면 `## 관련 소식` 폴백)에 맞게 그 테스트의 단정문을 갱신(개요 콜아웃 형식으로). 커버리지 약화 금지.
- [ ] **Step 5: 커밋** — `git add collector/topics.py tests/test_topics_render.py && git commit -m "feat(wiki): themed render (개요 콜아웃 + 테마 섹션 + 단신)"`

---

## Task 4: wiki.run_wiki가 구조 합성 사용

**Files:** Modify `collector/wiki.py`, Test `tests/test_wiki.py`

- [ ] **Step 1: 실패 테스트** — `tests/test_wiki.py`에 추가(또는 기존 합성 주입부 갱신): run_wiki가 구조 합성 결과로 themes를 채우는지.
```python
def test_run_wiki_builds_themes(tmp_path):
    from collector.models import Item
    from collector.store import append_items
    from collector.wiki import run_wiki
    from collector.topics import TopicStore
    items_store = str(tmp_path/"items.jsonl")
    append_items([Item(source_name="s", source_type="x", id=f"id{i}", title=f"T{i}",
                       link=f"http://{i}", published="2026-06-29", summary=f"s{i}",
                       categories=["AI"]) for i in (1,2)], items_store)
    def fake_struct(topic, items):
        return {"overview":"개요","themes":[{"name":"테마","intro":"정리","indexes":[1]}],
                "orphans":[2],"related":["Claude"]}
    run_wiki(items_store=items_store, classified_state=str(tmp_path/"c.json"),
             topics_path=str(tmp_path/"t.json"), out_dir=str(tmp_path/"topics"),
             classify=lambda it,k: it.categories, synthesize=fake_struct, resynth_threshold=1)
    d = TopicStore(str(tmp_path/"t.json")).data["AI"]
    assert d["themes"][0]["name"] == "테마"
    assert d["themes"][0]["item_ids"] == ["id1"]
    assert d["orphans"] == ["id2"]
```

- [ ] **Step 2: 실패 확인** — `pytest tests/test_wiki.py::test_run_wiki_builds_themes -v` → FAIL

- [ ] **Step 3: 구현** — `collector/wiki.py` 수정:
  1. import 변경: `from .wikisynth import synthesize_structure`
  2. `run_wiki(...)`의 `synthesize` 기본값을 `synthesize_structure`로.
  3. 재합성 블록 교체:
```python
    for tp in store.topic_names():
        if store.needs_resynth(tp, resynth_threshold) or not store.data[tp].get("themes"):
            try:
                r = synthesize(tp, store.data[tp]["items"])
                store.set_structure(tp, r["overview"], r["themes"], r["orphans"], r["related"])
            except Exception as e:
                print(f"[skip] 구조 합성 실패 {tp}: {e}")
```
  (기존 `not store.data[tp]["overview"]` 조건 → `not store.data[tp].get("themes")`로)

- [ ] **Step 4: 통과 확인** — `pytest tests/test_wiki.py -v` → PASS; 기존 test_wiki 케이스가 옛 `fake_synth`(튜플 반환)을 쓰면 구조 dict 반환으로 갱신. 전체 `pytest -q` PASS.
- [ ] **Step 5: 커밋** — `git add collector/wiki.py tests/test_wiki.py && git commit -m "feat(wiki): run_wiki uses synthesize_structure + set_structure"`

---

## Task 5: 재생성 + 검증 + 병합

- [ ] **Step 1: 강제 재합성** (기존 토픽을 테마 구조로) — 쿼터 필요(주제당 1회). `--resynth`로 전 주제 재합성:
```bash
cd "C:/ProjectS/ai-knowledge-assistant" && .venv/Scripts/python -m collector wiki --resynth
```
Expected: `[wiki] 0건 분류, N개 주제 페이지`. (429 뜨면 쿼터 소진 → 내일 자동 5시 또는 키 여유 시 재시도; 로직은 정상)

- [ ] **Step 2: 검증** — `head -30 "notes/topics/AI 모델·기술.md"` → `> [!abstract] 개요`, `## {테마이름}` 섹션들, 각 테마 아래 항목+요약, `## 짚어둘 단신`, `## 관련 주제` 확인.

- [ ] **Step 3: 커밋 + 푸시**
```bash
git add notes/topics && git commit -m "feat: regenerate topic pages in themed (정리형) format"
git push origin master
```

---

## 완료 정의
- 토픽 페이지가 **테마(소주제)별로 묶여** 정리된 글로 보인다(개요 콜아웃 + 테마 섹션 + 항목 내용 + 단신 + 관련주제).
- 넘버링 하드코딩·인라인 다이어그램 없음(옵시디언 Outline/그래프뷰가 처리).
- 합성은 주제당 1회 호출 유지(쿼터 영향 최소). 출처 링크는 코드가 렌더(환각 방지).
