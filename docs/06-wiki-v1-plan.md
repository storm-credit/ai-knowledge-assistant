# 주제별 자동정리 위키 v1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 수집된 항목을 AI가 주제별로 분류해 `notes/topics/<주제>.md` 위키 페이지로 자동 생성·갱신한다(하이브리드 갱신, 출처 링크, 다출처 신호, `[[링크]]`).

**Architecture:** 수집 항목을 `state/items.jsonl`에 구조화 저장 → `classify`가 LLM으로 주제 부여 → `TopicStore`(`state/topics.json`)가 단일 진실원천으로 주제별 데이터 보관 → 거기서 `notes/topics/*.md`를 렌더(마크다운 역파싱 없음). 분류 완료 추적은 기존 `StateStore` 재사용.

**Tech Stack:** Python 3.x, 기존 `openai`(Gemini flash-lite, 3키 로테이션), 표준 json/os, pytest.

---

## 파일 구조
```
collector/
  store.py     # 수집 항목 JSONL 저장/로드 (Item ↔ JSON)
  classify.py  # 항목 → 1~3 주제 (LLM)
  topics.py    # TopicStore(topics.json) + 마크다운 렌더
  wikisynth.py # 개요 재합성 (LLM)
  wiki.py      # 오케스트레이션 (분류→갱신→재합성→렌더)
  pipeline.py  # (수정) 수집 항목을 items.jsonl에도 저장
  __main__.py  # (수정) run / wiki 서브커맨드
tests/ ...
```

---

## Task 1: 항목 저장소 store.py

**Files:** Create `collector/store.py`, `tests/test_store.py`

- [ ] **Step 1: 실패 테스트**

`tests/test_store.py`:
```python
from collector.models import Item
from collector.store import append_items, load_items

def test_append_and_load_roundtrip(tmp_path):
    p = str(tmp_path / "items.jsonl")
    items = [Item(source_name="조코딩", source_type="youtube", id="a",
                  title="제목A", link="http://a", published="2026-06-27",
                  summary="요약A", tags=["t1"])]
    append_items(items, p)
    append_items([Item(source_name="SaaStr", source_type="newsletter", id="b",
                       title="제목B", link="http://b", published="", summary="요약B")], p)
    out = load_items(p)
    assert len(out) == 2
    assert out[0].id == "a" and out[0].summary == "요약A"
    assert out[1].source_name == "SaaStr"

def test_load_missing_returns_empty(tmp_path):
    assert load_items(str(tmp_path / "none.jsonl")) == []
```

- [ ] **Step 2: 실패 확인** — `.venv/Scripts/python -m pytest tests/test_store.py -v` → FAIL (No module named 'collector.store')

- [ ] **Step 3: 구현**

`collector/store.py`:
```python
import json, os
from dataclasses import asdict
from typing import List
from .models import Item

def append_items(items: List[Item], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(asdict(it), ensure_ascii=False) + "\n")

def load_items(path: str) -> List[Item]:
    if not os.path.exists(path):
        return []
    out: List[Item] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(Item(**json.loads(line)))
    return out
```

- [ ] **Step 4: 통과 확인** — `pytest tests/test_store.py -v` → PASS
- [ ] **Step 5: 커밋** — `git add collector/store.py tests/test_store.py && git commit -m "feat(wiki): structured item store (jsonl)"`

---

## Task 2: 파이프라인이 항목을 store에도 기록

**Files:** Modify `collector/pipeline.py`, Test `tests/test_pipeline_store.py`

- [ ] **Step 1: 실패 테스트**

`tests/test_pipeline_store.py`:
```python
from collector.config import SourcesConfig, Source
from collector.models import Item
from collector.state import StateStore
from collector.pipeline import run
from collector.store import load_items

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
```

- [ ] **Step 2: 실패 확인** — `pytest tests/test_pipeline_store.py -v` → FAIL (run() got unexpected keyword 'items_store')

- [ ] **Step 3: 구현** — `collector/pipeline.py` 수정:
  1. 상단 import 추가: `from .store import append_items`
  2. `run(...)` 시그니처에 파라미터 추가: `items_store: str = "state/items.jsonl"`
  3. `if new_items:` 블록 직전에 항목 저장 추가:

기존:
```python
    if new_items:
        path = write_digest(new_items, date=date, out_dir=out_dir)
```
수정:
```python
    if new_items:
        append_items(new_items, items_store)
        path = write_digest(new_items, date=date, out_dir=out_dir)
```

- [ ] **Step 4: 통과 확인** — `pytest tests/test_pipeline_store.py tests/test_pipeline.py -v` → 모두 PASS (기존 pipeline 테스트는 items_store 기본값으로 동작; tmp 경로 안 쓰는 기존 테스트는 기본 state/items.jsonl에 쓰므로, 기존 테스트가 깨지면 그 테스트에도 `items_store=str(tmp_path/'items.jsonl')` 인자를 추가한다)
- [ ] **Step 5: 커밋** — `git add collector/pipeline.py tests/test_pipeline_store.py && git commit -m "feat(wiki): pipeline persists items to store"`

---

## Task 3: 주제 분류 classify.py

**Files:** Create `collector/classify.py`, `tests/test_classify.py`

- [ ] **Step 1: 실패 테스트**

`tests/test_classify.py`:
```python
from collector.models import Item
from collector.classify import classify_item

class FakeResp:
    def __init__(self, c): self.choices=[type("C",(),{"message":type("M",(),{"content":c})})]
class FakeClient:
    def __init__(self, c): self._c=c; self.chat=type("Ch",(),{"completions":self})()
    def create(self, **k): return FakeResp(self._c)

def test_classify_returns_topics_max3():
    it = Item(source_name="조코딩", source_type="youtube", id="x",
              title="AI 에이전트 시대", link="l", published="", summary="에이전트 요약")
    out = classify_item(it, known_topics=["Claude"],
                        client=FakeClient("AI 에이전트, Claude, 바이브코딩, 여분"))
    assert out == ["AI 에이전트", "Claude", "바이브코딩"]  # 최대 3개, # 제거
```

- [ ] **Step 2: 실패 확인** — `pytest tests/test_classify.py -v` → FAIL (No module named 'collector.classify')

- [ ] **Step 3: 구현**

`collector/classify.py`:
```python
from typing import List
from .models import Item
from .summarize import _default_clients, _is_quota_error

CLASSIFY_PROMPT = (
    "다음 글을 1~3개의 주제로 분류해라. 기존 주제 목록에 맞는 게 있으면 가능한 그 중에서 고르고, "
    "없으면 새 주제명을 만들어라. 주제명은 짧은 한국어 명사구. "
    "쉼표로 구분해 주제명만 출력해라(설명·번호 금지).\n\n"
    "기존 주제: {known}\n제목: {title}\n요약: {summary}"
)

def classify_item(item: Item, known_topics: List[str], client=None, clients=None,
                  model: str = "gemini-2.5-flash-lite") -> List[str]:
    prompt = CLASSIFY_PROMPT.format(
        known=", ".join(known_topics) or "(없음)",
        title=item.title, summary=item.summary or item.raw_text[:500])
    cands = [client] if client is not None else (clients if clients is not None else _default_clients())
    last = None
    for c in cands:
        try:
            resp = c.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}])
            text = resp.choices[0].message.content.strip()
            parts = [p.strip().lstrip("#").strip() for p in text.replace("\n", ",").split(",")]
            return [p for p in parts if p][:3]
        except Exception as e:
            last = e
            if _is_quota_error(e):
                continue
            raise
    raise last
```

- [ ] **Step 4: 통과 확인** — `pytest tests/test_classify.py -v` → PASS
- [ ] **Step 5: 커밋** — `git add collector/classify.py tests/test_classify.py && git commit -m "feat(wiki): LLM topic classification with key rotation"`

---

## Task 4: TopicStore (topics.json)

**Files:** Create `collector/topics.py`, `tests/test_topics.py`

- [ ] **Step 1: 실패 테스트**

`tests/test_topics.py`:
```python
from collector.models import Item
from collector.topics import TopicStore

def mk(id, src, title): 
    return Item(source_name=src, source_type="x", id=id, title=title,
                link="http://"+id, published="2026-06-27", summary="요약-"+id)

def test_add_dedup_sources_and_resynth(tmp_path):
    s = TopicStore(str(tmp_path / "topics.json"))
    assert s.add_item("AI 에이전트", mk("a","조코딩","글a")) is True
    assert s.add_item("AI 에이전트", mk("a","조코딩","글a")) is False  # 중복 id
    assert s.add_item("AI 에이전트", mk("b","SaaStr","글b")) is True
    d = s.data["AI 에이전트"]
    assert len(d["items"]) == 2
    assert sorted(d["sources"]) == ["SaaStr", "조코딩"]   # 출처 2개
    assert s.needs_resynth("AI 에이전트", threshold=2) is True
    s.set_overview("AI 에이전트", "개요글", ["Claude"])
    assert s.needs_resynth("AI 에이전트", threshold=2) is False  # 카운터 리셋
    s.save()
    assert TopicStore(str(tmp_path / "topics.json")).data["AI 에이전트"]["overview"] == "개요글"
```

- [ ] **Step 2: 실패 확인** — `pytest tests/test_topics.py -v` → FAIL (No module named 'collector.topics')

- [ ] **Step 3: 구현**

`collector/topics.py`:
```python
import json, os
from typing import Dict, List
from .models import Item

def _empty():
    return {"items": [], "sources": [], "overview": "", "related": [], "new_since_synth": 0}

class TopicStore:
    def __init__(self, path: str):
        self.path = path
        self.data: Dict[str, dict] = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self.data = json.load(f)

    def topic_names(self) -> List[str]:
        return list(self.data.keys())

    def add_item(self, topic: str, item: Item) -> bool:
        t = self.data.setdefault(topic, _empty())
        if any(i["id"] == item.id for i in t["items"]):
            return False
        t["items"].append({"id": item.id, "title": item.title, "link": item.link,
                           "source": item.source_name, "date": item.published or "",
                           "summary": item.summary or ""})
        if item.source_name not in t["sources"]:
            t["sources"].append(item.source_name)
        t["new_since_synth"] += 1
        return True

    def needs_resynth(self, topic: str, threshold: int = 5) -> bool:
        return self.data.get(topic, {}).get("new_since_synth", 0) >= threshold

    def set_overview(self, topic: str, overview: str, related: List[str]) -> None:
        t = self.data[topic]
        t["overview"] = overview
        t["related"] = related
        t["new_since_synth"] = 0

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: 통과 확인** — `pytest tests/test_topics.py -v` → PASS
- [ ] **Step 5: 커밋** — `git add collector/topics.py tests/test_topics.py && git commit -m "feat(wiki): TopicStore with dedup/source-count/resynth"`

---

## Task 5: 주제 페이지 렌더

**Files:** Modify `collector/topics.py`, Test `tests/test_topics_render.py`

- [ ] **Step 1: 실패 테스트**

`tests/test_topics_render.py`:
```python
from collector.models import Item
from collector.topics import TopicStore, render_page, write_pages

def test_render_and_write(tmp_path):
    s = TopicStore(str(tmp_path/"topics.json"))
    s.add_item("AI 에이전트", Item(source_name="조코딩", source_type="x", id="a",
               title="글a", link="http://a", published="2026-06-27", summary="요약a"))
    s.set_overview("AI 에이전트", "이 주제 개요입니다", ["Claude", "SaaS"])
    md = render_page("AI 에이전트", s.data["AI 에이전트"])
    assert "# AI 에이전트" in md
    assert "1개 출처" in md
    assert "이 주제 개요입니다" in md
    assert "[글a](http://a)" in md
    assert "[[Claude]]" in md and "[[SaaS]]" in md

    paths = write_pages(s, str(tmp_path/"topics"))
    assert any(p.endswith("AI 에이전트.md") for p in paths)
```

- [ ] **Step 2: 실패 확인** — `pytest tests/test_topics_render.py -v` → FAIL (cannot import render_page)

- [ ] **Step 3: 구현** — `collector/topics.py` 맨 아래에 추가:
```python
import re as _re

def render_page(topic: str, t: dict) -> str:
    lines = [f"# {topic}", "", f"> 📌 {len(t['sources'])}개 출처에서 언급", ""]
    if t.get("overview"):
        lines += ["## 개요", t["overview"], ""]
    lines.append("## 관련 소식")
    for it in reversed(t["items"]):   # 최신 먼저
        date = (it.get("date") or "")[:10]
        lines.append(f"- {date} · {it['source']}: [{it['title']}]({it['link']})")
    lines.append("")
    if t.get("related"):
        lines += ["## 관련 주제", " · ".join(f"[[{r}]]" for r in t["related"]), ""]
    return "\n".join(lines).rstrip() + "\n"

def write_pages(store: "TopicStore", out_dir: str) -> list:
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for topic, t in store.data.items():
        safe = _re.sub(r'[\\/:*?"<>|]', "_", topic).strip() or "untitled"
        p = os.path.join(out_dir, f"{safe}.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write(render_page(topic, t))
        paths.append(p)
    return paths
```

- [ ] **Step 4: 통과 확인** — `pytest tests/test_topics_render.py -v` → PASS
- [ ] **Step 5: 커밋** — `git add collector/topics.py tests/test_topics_render.py && git commit -m "feat(wiki): render topic pages to markdown"`

---

## Task 6: 개요 재합성 wikisynth.py

**Files:** Create `collector/wikisynth.py`, `tests/test_wikisynth.py`

- [ ] **Step 1: 실패 테스트**

`tests/test_wikisynth.py`:
```python
from collector.wikisynth import synthesize_overview

class FakeResp:
    def __init__(self,c): self.choices=[type("C",(),{"message":type("M",(),{"content":c})})]
class FakeClient:
    def __init__(self,c): self._c=c; self.chat=type("Ch",(),{"completions":self})()
    def create(self,**k): return FakeResp(self._c)

def test_synthesize_parses_overview_and_related():
    items = [{"title":"글a","summary":"요약a"},{"title":"글b","summary":"요약b"}]
    fake = FakeClient("개요: 이것은 정리된 개요다.\n관련주제: Claude, SaaS")
    ov, rel = synthesize_overview("AI 에이전트", items, client=fake)
    assert "정리된 개요" in ov
    assert rel == ["Claude", "SaaS"]
```

- [ ] **Step 2: 실패 확인** — `pytest tests/test_wikisynth.py -v` → FAIL

- [ ] **Step 3: 구현**

`collector/wikisynth.py`:
```python
from typing import List, Tuple
from .summarize import _default_clients, _is_quota_error

SYNTH_PROMPT = (
    "다음은 '{topic}' 주제로 모인 항목들이다. 이를 바탕으로 한국어로 정리하라.\n"
    "1) 첫 줄에 '개요: '로 시작해 3~5문장 요약.\n"
    "2) 다음 줄에 '관련주제: '로 시작해 관련될 만한 다른 주제 2~4개를 쉼표로.\n"
    "원문에 없는 사실은 지어내지 마라.\n\n항목들:\n{items}"
)

def synthesize_overview(topic: str, items: List[dict], client=None, clients=None,
                        model: str = "gemini-2.5-flash-lite") -> Tuple[str, List[str]]:
    body = "\n".join(f"- {i.get('title','')}: {i.get('summary','')}" for i in items)[:8000]
    prompt = SYNTH_PROMPT.format(topic=topic, items=body)
    cands = [client] if client is not None else (clients if clients is not None else _default_clients())
    last = None
    for c in cands:
        try:
            resp = c.chat.completions.create(model=model, messages=[{"role":"user","content":prompt}])
            text = resp.choices[0].message.content.strip()
            overview, related = "", []
            for line in text.splitlines():
                s = line.strip()
                if s.startswith("개요:"):
                    overview = s[len("개요:"):].strip()
                elif s.startswith("관련주제:"):
                    related = [x.strip().lstrip("#").strip()
                               for x in s[len("관련주제:"):].split(",") if x.strip()]
            if not overview:
                overview = text   # 형식 안 맞으면 통째로
            return overview, related[:4]
        except Exception as e:
            last = e
            if _is_quota_error(e):
                continue
            raise
    raise last
```

- [ ] **Step 4: 통과 확인** — `pytest tests/test_wikisynth.py -v` → PASS
- [ ] **Step 5: 커밋** — `git add collector/wikisynth.py tests/test_wikisynth.py && git commit -m "feat(wiki): LLM overview synthesis per topic"`

---

## Task 7: 오케스트레이션 wiki.py

**Files:** Create `collector/wiki.py`, `tests/test_wiki.py`

- [ ] **Step 1: 실패 테스트**

`tests/test_wiki.py`:
```python
from collector.models import Item
from collector.store import append_items
from collector.wiki import run_wiki

def mk(id, title): return Item(source_name="조코딩", source_type="x", id=id,
                               title=title, link="http://"+id, published="2026-06-27", summary="요약")

def test_run_wiki_classifies_and_writes(tmp_path):
    items_store = str(tmp_path/"items.jsonl")
    append_items([mk("a","에이전트 글"), mk("b","Claude 글")], items_store)

    def fake_classify(item, known): 
        return ["AI 에이전트"] if "에이전트" in item.title else ["Claude"]
    def fake_synth(topic, items): return (f"{topic} 개요", ["기타"])

    paths = run_wiki(items_store=items_store,
                     classified_state=str(tmp_path/"classified.json"),
                     topics_path=str(tmp_path/"topics.json"),
                     out_dir=str(tmp_path/"topics"),
                     classify=fake_classify, synthesize=fake_synth, resynth_threshold=1)
    names = [p.split("\\")[-1].split("/")[-1] for p in paths]
    assert "AI 에이전트.md" in names and "Claude.md" in names

    # 재실행 시 이미 분류된 건 건너뜀 (새 0건)
    paths2 = run_wiki(items_store=items_store,
                      classified_state=str(tmp_path/"classified.json"),
                      topics_path=str(tmp_path/"topics.json"),
                      out_dir=str(tmp_path/"topics"),
                      classify=fake_classify, synthesize=fake_synth, resynth_threshold=1)
    # 페이지는 여전히 렌더되지만, items.jsonl의 두 항목은 재분류 안 됨
    import json
    cl = json.load(open(str(tmp_path/"classified.json"), encoding="utf-8"))
    assert set(cl["seen"]) == {"a", "b"}
```

- [ ] **Step 2: 실패 확인** — `pytest tests/test_wiki.py -v` → FAIL (No module named 'collector.wiki')

- [ ] **Step 3: 구현**

`collector/wiki.py`:
```python
from typing import Callable, List
from .store import load_items
from .state import StateStore
from .topics import TopicStore, write_pages
from .classify import classify_item
from .wikisynth import synthesize_overview

def run_wiki(items_store: str = "state/items.jsonl",
             classified_state: str = "state/classified.json",
             topics_path: str = "state/topics.json",
             out_dir: str = "notes/topics",
             classify: Callable = classify_item,
             synthesize: Callable = synthesize_overview,
             resynth_threshold: int = 5) -> List[str]:
    items = load_items(items_store)
    seen = StateStore(classified_state)
    store = TopicStore(topics_path)
    known = store.topic_names()

    new = [it for it in items if seen.is_new(it.id)]
    for it in new:
        try:
            topics = classify(it, known)
        except Exception as e:
            print(f"[skip] 분류 실패 {it.title[:30]}: {e}")
            continue
        for tp in topics:
            store.add_item(tp, it)
            if tp not in known:
                known.append(tp)
        seen.mark_seen(it.id)

    for tp in store.topic_names():
        if store.needs_resynth(tp, resynth_threshold) or not store.data[tp]["overview"]:
            try:
                ov, rel = synthesize(tp, store.data[tp]["items"])
                store.set_overview(tp, ov, rel)
            except Exception as e:
                print(f"[skip] 개요 합성 실패 {tp}: {e}")

    store.save()
    seen.save()
    paths = write_pages(store, out_dir)
    print(f"[wiki] {len(new)}건 분류, {len(paths)}개 주제 페이지 → {out_dir}")
    return paths
```

- [ ] **Step 4: 통과 확인** — `pytest tests/test_wiki.py -v` → PASS; 그리고 `pytest -q` 전체 PASS
- [ ] **Step 5: 커밋** — `git add collector/wiki.py tests/test_wiki.py && git commit -m "feat(wiki): orchestrate classify->update->synth->render"`

---

## Task 8: CLI 서브커맨드 (run / wiki)

**Files:** Modify `collector/__main__.py`

- [ ] **Step 1: 구현** — `collector/__main__.py` 전체 교체:
```python
import sys, datetime
from .config import load_sources
from .state import StateStore
from .pipeline import run
from .wiki import run_wiki

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    today = datetime.date.today().isoformat()
    if cmd in ("run", "all"):
        cfg = load_sources("sources.yaml")
        state = StateStore("state/seen.json")
        run(cfg, state, out_dir="notes/daily", date=today)
        run_wiki()                      # 수집 후 위키 갱신
    elif cmd == "wiki":
        run_wiki()
    else:
        print(f"알 수 없는 명령: {cmd} (run | wiki)")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 확인** — `.venv/Scripts/python -m collector badcmd` → "알 수 없는 명령" 출력하고 종료코드 1
- [ ] **Step 3: 커밋** — `git add collector/__main__.py && git commit -m "feat(wiki): add 'wiki' subcommand; daily run updates wiki"`

---

## Task 9: 백필 + 실제 실행 + 검증

- [ ] **Step 1: 기존 수집분 백필** — 1단계는 items.jsonl 없이 돌았으므로, 오늘 다이제스트의 항목을 store에 채운다. `state/items.jsonl`이 비었으면 한 번만 재수집(중복은 seen으로 걸러짐 → 비어있을 수 있음). 따라서 백필 스크립트로 `notes/daily/2026-06-27.md`를 읽어 Item으로 변환해 `append_items`로 저장하거나, 간단히 **state 초기화 후 재수집**:
```bash
cd "C:/ProjectS/ai-knowledge-assistant"
rm -f state/seen.json state/items.jsonl
.venv/Scripts/python -m collector run
```
Expected: 수집·요약되며 `state/items.jsonl`에 항목 저장 + `[wiki] N건 분류 ...` 출력

- [ ] **Step 2: 결과 검증** — `notes/topics/*.md` 생성 확인:
```bash
ls notes/topics/ ; head -40 "notes/topics/$(ls notes/topics | head -1)"
```
Expected: 주제별 .md 여러 개, 각 파일에 `# 주제`, `📌 N개 출처`, `## 관련 소식`, `[[링크]]`

- [ ] **Step 3: 재실행 멱등성** — `.venv/Scripts/python -m collector wiki` 재실행 → `[wiki] 0건 분류` (이미 분류됨)

- [ ] **Step 4: .gitignore 확인** — `state/`는 이미 ignore됨(topics.json·classified.json·items.jsonl 포함). `notes/topics/`는 커밋 대상.

- [ ] **Step 5: 커밋 + 푸시**
```bash
git add notes/topics && git commit -m "feat: first topic-wiki pages generated"
git push origin master
```

---

## 완료 정의 (v1)
- `python -m collector wiki`(및 daily `run`)가 수집 항목을 **주제별 `notes/topics/*.md`**로 분류·정리한다.
- 같은 항목은 재분류되지 않고(멱등), 주제에 새 글이 오면 누적되며 출처 수가 는다.
- 각 페이지에 개요·관련 소식(출처 링크)·`[[관련 주제]]`가 있고 옵시디언 그래프로 연결된다.
- 매일 5시 자동 실행에 위키 갱신이 포함된다.
