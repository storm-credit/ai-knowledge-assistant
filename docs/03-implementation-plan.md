# 1단계 수집기 (Phase-1 Collector) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 매일 새벽 5시에 지정한 유튜브/뉴스레터의 새 글을 수집·한국어 요약해서 `notes/daily/YYYY-MM-DD.md`로 저장한다(중복 없이).

**Architecture:** 표준 Python 패키지 `collector/`가 결정적(deterministic) 부분(설정·RSS수집·중복제거·저장)을 담당하고, 요약만 Gemini를 호출한다. 단발 실행 CLI(`python -m collector run`)를 Windows 작업 스케줄러가 매일 5시에 돌린다. Hermes 에이전트는 2단계(Q&A)부터 본격 사용.

**Tech Stack:** Python 3.11+, feedparser(RSS), youtube-transcript-api(자막, 실패 시 설명으로 폴백), openai(Gemini OpenAI-호환 엔드포인트), PyYAML, pytest.

---

## A. 구성요소 결정표 (← PM 검토 지점, 확정)

| 부품(요구사항) | 구현 방법 | 스킬 | MCP | 훅 |
|---|---|---|---|---|
| ② 수집(RSS) | `feedparser` | — | ❌ 불필요 | — |
| 유튜브 자막 | `youtube-transcript-api` (실패 시 RSS 설명 폴백) | (watch 스킬 대신 경량 라이브러리) | ❌ | — |
| ③ 요약 | Gemini `gemini-2.5-flash` (openai 라이브러리, OpenAI-호환 엔드포인트) | — | ❌ | — |
| 🔖 상태추적 | `state/seen.json` (본 항목 ID 집합) | — | ❌ | — |
| ④ 저장 | `notes/daily/*.md` 파일 쓰기 | — | ❌ | — |
| 📩 전달 | 마크다운 1장 (1단계) | — | ❌ | — |
| 스케줄 | Windows 작업 스케줄러 (대안: Hermes Cron) | — | — | — |

> 원칙대로 **Hermes 기본/표준 도구로 되는 건 MCP·훅 안 붙임.** 1단계엔 둘 다 불필요.

## B. 빌드 팀(서브에이전트) 배정

`subagent-driven-development`로 태스크별 신규 서브에이전트 + 2단계 리뷰. (아키텍트/코더/리뷰어 역할)

## C. 파일 구조

```
ai-knowledge-assistant/
├─ collector/
│  ├─ __init__.py
│  ├─ models.py        # Item 데이터클래스
│  ├─ config.py        # sources.yaml 로드
│  ├─ state.py         # 본 항목 ID 저장/조회 (중복제거)
│  ├─ feeds.py         # RSS 파싱 → Item 목록
│  ├─ enrich.py        # 유튜브 자막 가져오기(+폴백)
│  ├─ summarize.py     # Gemini 요약 (클라이언트 주입 → 테스트 가능)
│  ├─ digest.py        # 마크다운 렌더 + 저장
│  ├─ pipeline.py      # 전체 조립
│  └─ __main__.py      # CLI: python -m collector run
├─ sources.yaml        # 출처 설정
├─ tests/              # pytest
├─ requirements.txt
└─ notes/daily/        # 출력 (이미 존재)
```

각 파일은 책임 하나. 테스트로 독립 검증 가능.

---

## Task 1: 프로젝트 골격 + 의존성 + Item 모델

**Files:**
- Create: `requirements.txt`
- Create: `collector/__init__.py`
- Create: `collector/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: requirements.txt 작성**

```
feedparser==6.0.11
youtube-transcript-api==0.6.2
openai==1.51.0
PyYAML==6.0.2
pytest==8.3.3
```

- [ ] **Step 2: 가상환경 + 설치**

Run:
```bash
cd "C:/ProjectS/ai-knowledge-assistant" && python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
```
Expected: 설치 성공 (`Successfully installed feedparser... pytest...`)

- [ ] **Step 3: 실패 테스트 작성 — Item 모델**

`tests/test_models.py`:
```python
from collector.models import Item

def test_item_holds_fields_and_summary_defaults_empty():
    it = Item(source_name="조코딩", source_type="youtube",
              id="yt:abc", title="제목", link="http://x", published="2026-06-27",
              raw_text="원문")
    assert it.summary == ""
    assert it.tags == []
    assert it.id == "yt:abc"
```

- [ ] **Step 4: 테스트 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_models.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'collector.models'`)

- [ ] **Step 5: 구현 — collector/__init__.py (빈 파일) + collector/models.py**

`collector/__init__.py`: (빈 파일)

`collector/models.py`:
```python
from dataclasses import dataclass, field
from typing import List

@dataclass
class Item:
    source_name: str
    source_type: str   # "youtube" | "newsletter"
    id: str            # 중복제거용 고유 ID
    title: str
    link: str
    published: str
    raw_text: str = ""     # 요약 대상 원문(설명/자막)
    summary: str = ""      # 채워질 요약
    tags: List[str] = field(default_factory=list)
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 7: 커밋**

```bash
git add requirements.txt collector/__init__.py collector/models.py tests/test_models.py
git commit -m "feat(collector): add Item model + project skeleton"
```

---

## Task 2: 설정 로더 (sources.yaml)

**Files:**
- Create: `collector/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_config.py`:
```python
from collector.config import load_sources

def test_load_sources_parses_youtube_and_newsletters(tmp_path):
    p = tmp_path / "sources.yaml"
    p.write_text(
        "youtube:\n"
        "  - name: 조코딩\n"
        "    channel_id: UC123\n"
        "newsletters:\n"
        "  - name: SaaStr\n"
        "    rss: https://www.saastr.com/feed\n",
        encoding="utf-8")
    cfg = load_sources(str(p))
    assert cfg.youtube[0].name == "조코딩"
    assert cfg.youtube[0].rss == "https://www.youtube.com/feeds/videos.xml?channel_id=UC123"
    assert cfg.newsletters[0].rss == "https://www.saastr.com/feed"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: FAIL (`No module named 'collector.config'`)

- [ ] **Step 3: 구현**

`collector/config.py`:
```python
from dataclasses import dataclass
from typing import List
import yaml

YT_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={}"

@dataclass
class Source:
    name: str
    rss: str
    type: str

@dataclass
class SourcesConfig:
    youtube: List[Source]
    newsletters: List[Source]

def load_sources(path: str) -> SourcesConfig:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    yt = [Source(name=e["name"], rss=YT_FEED.format(e["channel_id"]), type="youtube")
          for e in data.get("youtube", [])]
    nl = [Source(name=e["name"], rss=e["rss"], type="newsletter")
          for e in data.get("newsletters", [])]
    return SourcesConfig(youtube=yt, newsletters=nl)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add collector/config.py tests/test_config.py
git commit -m "feat(collector): load sources.yaml into typed config"
```

---

## Task 3: 상태 저장소 (중복 제거)

**Files:**
- Create: `collector/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_state.py`:
```python
from collector.state import StateStore

def test_new_item_then_marked_then_not_new(tmp_path):
    path = tmp_path / "seen.json"
    s = StateStore(str(path))
    assert s.is_new("yt:abc") is True
    s.mark_seen("yt:abc")
    s.save()

    s2 = StateStore(str(path))   # 새로 로드해도 기억
    assert s2.is_new("yt:abc") is False
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_state.py -v`
Expected: FAIL (`No module named 'collector.state'`)

- [ ] **Step 3: 구현**

`collector/state.py`:
```python
import json, os
from typing import Set

class StateStore:
    def __init__(self, path: str):
        self.path = path
        self._seen: Set[str] = set()
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self._seen = set(json.load(f).get("seen", []))

    def is_new(self, item_id: str) -> bool:
        return item_id not in self._seen

    def mark_seen(self, item_id: str) -> None:
        self._seen.add(item_id)

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"seen": sorted(self._seen)}, f, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_state.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add collector/state.py tests/test_state.py
git commit -m "feat(collector): persistent seen-id store for dedup"
```

---

## Task 4: RSS 수집기

**Files:**
- Create: `collector/feeds.py`
- Create: `tests/test_feeds.py`

- [ ] **Step 1: 실패 테스트 작성** (feedparser는 문자열 파싱 가능 → 고정 픽스처 사용)

`tests/test_feeds.py`:
```python
from collector.config import Source
from collector.feeds import parse_feed

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>새 글 제목</title>
    <link>https://example.com/a</link>
    <guid>guid-a</guid>
    <pubDate>Fri, 27 Jun 2026 00:00:00 +0000</pubDate>
    <description>본문 설명입니다</description>
  </item>
</channel></rss>"""

def test_parse_feed_maps_entries_to_items():
    src = Source(name="SaaStr", rss="x", type="newsletter")
    items = parse_feed(RSS, src)
    assert len(items) == 1
    it = items[0]
    assert it.title == "새 글 제목"
    assert it.id == "guid-a"
    assert it.source_name == "SaaStr"
    assert "본문 설명" in it.raw_text
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_feeds.py -v`
Expected: FAIL (`No module named 'collector.feeds'`)

- [ ] **Step 3: 구현**

`collector/feeds.py`:
```python
import feedparser
from typing import List
from .config import Source
from .models import Item

def parse_feed(source_or_xml, src: Source) -> List[Item]:
    """source_or_xml: RSS XML 문자열 또는 URL (feedparser가 둘 다 처리)."""
    parsed = feedparser.parse(source_or_xml)
    items: List[Item] = []
    for e in parsed.entries:
        item_id = getattr(e, "id", None) or getattr(e, "link", "") or e.get("title", "")
        items.append(Item(
            source_name=src.name,
            source_type=src.type,
            id=item_id,
            title=e.get("title", "(제목 없음)"),
            link=e.get("link", ""),
            published=e.get("published", ""),
            raw_text=e.get("summary", "") or e.get("description", ""),
        ))
    return items

def fetch_feed(src: Source) -> List[Item]:
    return parse_feed(src.rss, src)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_feeds.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add collector/feeds.py tests/test_feeds.py
git commit -m "feat(collector): parse RSS feeds into Items"
```

---

## Task 5: 유튜브 자막 보강 (실패 시 폴백)

**Files:**
- Create: `collector/enrich.py`
- Create: `tests/test_enrich.py`

- [ ] **Step 1: 실패 테스트 작성** (자막 API는 주입형 함수로 모킹)

`tests/test_enrich.py`:
```python
from collector.models import Item
from collector.enrich import enrich_youtube

def make_item():
    return Item(source_name="조코딩", source_type="youtube",
                id="yt", title="t", link="https://www.youtube.com/watch?v=VID",
                published="", raw_text="원래 설명")

def test_enrich_uses_transcript_when_available():
    it = enrich_youtube(make_item(), fetch_transcript=lambda vid: "자막 내용 " + vid)
    assert "자막 내용 VID" in it.raw_text

def test_enrich_falls_back_to_description_on_failure():
    def boom(vid): raise RuntimeError("no captions")
    it = enrich_youtube(make_item(), fetch_transcript=boom)
    assert it.raw_text == "원래 설명"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_enrich.py -v`
Expected: FAIL (`No module named 'collector.enrich'`)

- [ ] **Step 3: 구현**

`collector/enrich.py`:
```python
import re
from typing import Callable, Optional
from .models import Item

def _video_id(url: str) -> Optional[str]:
    m = re.search(r"[?&]v=([\w-]+)", url)
    return m.group(1) if m else None

def _default_fetch_transcript(video_id: str) -> str:
    from youtube_transcript_api import YouTubeTranscriptApi
    parts = YouTubeTranscriptApi.get_transcript(video_id, languages=["ko", "en"])
    return " ".join(p["text"] for p in parts)

def enrich_youtube(item: Item, fetch_transcript: Callable[[str], str] = _default_fetch_transcript) -> Item:
    vid = _video_id(item.link)
    if not vid:
        return item
    try:
        text = fetch_transcript(vid)
        if text.strip():
            item.raw_text = text
    except Exception:
        pass  # 자막 없거나 실패 → 기존 설명 유지 (폴백)
    return item
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_enrich.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add collector/enrich.py tests/test_enrich.py
git commit -m "feat(collector): youtube transcript enrichment with fallback"
```

---

## Task 6: 요약기 (Gemini)

**Files:**
- Create: `collector/summarize.py`
- Create: `tests/test_summarize.py`

- [ ] **Step 1: 실패 테스트 작성** (LLM 클라이언트 주입 → 가짜로 모킹)

`tests/test_summarize.py`:
```python
from collector.models import Item
from collector.summarize import summarize_item

class FakeResp:
    def __init__(self, content):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})})]

class FakeClient:
    def __init__(self, content):
        self._content = content
        self.chat = type("Chat", (), {"completions": self})()
    def create(self, **kwargs):
        return FakeResp(self._content)

def test_summarize_fills_summary_field():
    it = Item(source_name="조코딩", source_type="youtube", id="x",
              title="제목", link="l", published="", raw_text="긴 원문")
    fake = FakeClient("- 핵심 요약 한 줄")
    out = summarize_item(it, client=fake, model="gemini-2.5-flash")
    assert "핵심 요약" in out.summary
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_summarize.py -v`
Expected: FAIL (`No module named 'collector.summarize'`)

- [ ] **Step 3: 구현**

`collector/summarize.py`:
```python
import os
from .models import Item

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"

def _default_client():
    from openai import OpenAI
    return OpenAI(api_key=os.environ["GEMINI_API_KEY"], base_url=GEMINI_BASE)

PROMPT = (
    "다음 콘텐츠를 한국어로 3줄 이내로 핵심만 요약하고, 마지막 줄에 "
    "관련 주제 태그를 #해시태그 형식으로 3개 이하 붙여라.\n\n"
    "제목: {title}\n출처: {source}\n내용:\n{body}"
)

def summarize_item(item: Item, client=None, model: str = "gemini-2.5-flash") -> Item:
    client = client or _default_client()
    body = (item.raw_text or item.title)[:6000]
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": PROMPT.format(
            title=item.title, source=item.source_name, body=body)}],
    )
    item.summary = resp.choices[0].message.content.strip()
    return item
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_summarize.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add collector/summarize.py tests/test_summarize.py
git commit -m "feat(collector): Gemini summarizer with injectable client"
```

---

## Task 7: 다이제스트 작성기

**Files:**
- Create: `collector/digest.py`
- Create: `tests/test_digest.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_digest.py`:
```python
from collector.models import Item
from collector.digest import render_markdown, write_digest

def test_render_groups_by_source_and_includes_summary():
    items = [
        Item(source_name="조코딩", source_type="youtube", id="1",
             title="영상A", link="http://y/a", published="", summary="- 요약A"),
        Item(source_name="SaaStr", source_type="newsletter", id="2",
             title="글B", link="http://s/b", published="", summary="- 요약B"),
    ]
    md = render_markdown(items, date="2026-06-27")
    assert "# 2026-06-27 AI 요약" in md
    assert "조코딩" in md and "SaaStr" in md
    assert "요약A" in md and "[영상A](http://y/a)" in md

def test_write_digest_creates_dated_file(tmp_path):
    items = [Item(source_name="조코딩", source_type="youtube", id="1",
                  title="영상A", link="http://y/a", published="", summary="- 요약A")]
    path = write_digest(items, date="2026-06-27", out_dir=str(tmp_path))
    assert path.endswith("2026-06-27.md")
    with open(path, encoding="utf-8") as f:
        assert "요약A" in f.read()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_digest.py -v`
Expected: FAIL (`No module named 'collector.digest'`)

- [ ] **Step 3: 구현**

`collector/digest.py`:
```python
import os
from collections import defaultdict
from typing import List
from .models import Item

def render_markdown(items: List[Item], date: str) -> str:
    lines = [f"# {date} AI 요약", "", f"> 총 {len(items)}건", ""]
    by_source = defaultdict(list)
    for it in items:
        by_source[it.source_name].append(it)
    for source, group in by_source.items():
        lines.append(f"## {source}")
        for it in group:
            lines.append(f"### [{it.title}]({it.link})")
            lines.append(it.summary or "(요약 없음)")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"

def write_digest(items: List[Item], date: str, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{date}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_markdown(items, date))
    return path
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_digest.py -v`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add collector/digest.py tests/test_digest.py
git commit -m "feat(collector): render and write daily markdown digest"
```

---

## Task 8: 파이프라인 조립

**Files:**
- Create: `collector/pipeline.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: 실패 테스트 작성** (수집·요약을 주입형으로 → 네트워크/LLM 없이 검증)

`tests/test_pipeline.py`:
```python
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
               fetch=fake_fetch, summarize=fake_summarize, enrich=lambda i: i)

    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "신규" in content and "이전" not in content   # 새 것만
    assert state.is_new("new") is False                   # 이제 본 것으로 기록
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline.py -v`
Expected: FAIL (`No module named 'collector.pipeline'`)

- [ ] **Step 3: 구현**

`collector/pipeline.py`:
```python
from typing import Callable, List
from .config import SourcesConfig, Source
from .models import Item
from .state import StateStore
from .feeds import fetch_feed
from .enrich import enrich_youtube
from .summarize import summarize_item
from .digest import write_digest

def run(cfg: SourcesConfig, state: StateStore, out_dir: str, date: str,
        fetch: Callable[[Source], List[Item]] = fetch_feed,
        enrich: Callable[[Item], Item] = enrich_youtube,
        summarize: Callable[[Item], Item] = summarize_item) -> str:
    new_items: List[Item] = []
    for src in (cfg.youtube + cfg.newsletters):
        try:
            items = fetch(src)
        except Exception as e:
            print(f"[skip] {src.name} 수집 실패: {e}")   # 개별 실패 격리
            continue
        for it in items:
            if not state.is_new(it.id):
                continue
            if it.source_type == "youtube":
                it = enrich(it)
            try:
                it = summarize(it)
            except Exception as e:
                it.summary = f"(요약 실패: {e})"
            new_items.append(it)
            state.mark_seen(it.id)

    path = write_digest(new_items, date=date, out_dir=out_dir)
    state.save()
    print(f"[done] {len(new_items)}건 → {path}")
    return path
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline.py -v`
Expected: PASS

- [ ] **Step 5: 전체 테스트 통과 확인**

Run: `.venv/Scripts/python -m pytest -v`
Expected: 모든 테스트 PASS

- [ ] **Step 6: 커밋**

```bash
git add collector/pipeline.py tests/test_pipeline.py
git commit -m "feat(collector): orchestrate fetch->dedup->enrich->summarize->write"
```

---

## Task 9: CLI 엔트리 + 실제 sources.yaml

**Files:**
- Create: `collector/__main__.py`
- Create: `sources.yaml`

- [ ] **Step 1: CLI 작성**

`collector/__main__.py`:
```python
import sys, datetime
from .config import load_sources
from .state import StateStore
from .pipeline import run

def main():
    cfg = load_sources("sources.yaml")
    state = StateStore("state/seen.json")
    today = datetime.date.today().isoformat()
    run(cfg, state, out_dir="notes/daily", date=today)

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: sources.yaml 작성** (채널 ID는 설정 시 확정 — 채널 페이지 소스에서 `"channelId"` 검색해 채움)

`sources.yaml`:
```yaml
# 유튜브: channel_id는 채널 페이지 소스보기에서 "channelId":"UC..." 검색해 채움
youtube:
  - name: 노정석
    channel_id: REPLACE_UC_노정석
  - name: 윤자동
    channel_id: REPLACE_UC_윤자동
  - name: 조코딩
    channel_id: REPLACE_UC_조코딩
  - name: TTimesTV
    channel_id: REPLACE_UC_TTimesTV
  - name: 안될공학
    channel_id: REPLACE_UC_안될공학
newsletters:
  - name: SaaStr
    rss: https://www.saastr.com/feed
  - name: Lenny's Newsletter
    rss: https://www.lennysnewsletter.com/feed
  - name: a16z
    rss: https://a16z.com/feed/
```

- [ ] **Step 3: 채널 ID 확정** — 5개 유튜브 채널의 실제 `UC...` ID를 찾아 `REPLACE_...`를 교체하고, 각 RSS URL이 200 응답하는지 확인.

Run (예시 확인):
```bash
.venv/Scripts/python -c "import feedparser; d=feedparser.parse('https://www.saastr.com/feed'); print(len(d.entries), '항목')"
```
Expected: `N 항목` (N>0)

- [ ] **Step 4: 커밋**

```bash
git add collector/__main__.py sources.yaml
git commit -m "feat(collector): CLI entrypoint + sources config"
```

---

## Task 10: 스케줄 등록 (Windows 작업 스케줄러)

**Files:**
- Create: `run_collector.bat`
- Modify: `.gitignore` (state/ 추가)

- [ ] **Step 1: 실행 배치 작성**

`run_collector.bat`:
```bat
@echo off
cd /d C:\ProjectS\ai-knowledge-assistant
.venv\Scripts\python.exe -m collector run >> logs\collector.log 2>&1
```

- [ ] **Step 2: .gitignore에 런타임 상태/로그 제외 추가**

`.gitignore` 끝에 추가:
```
state/
logs/
```

- [ ] **Step 3: 작업 스케줄러 등록** (매일 05:00)

Run (PowerShell, 관리자):
```powershell
$action = New-ScheduledTaskAction -Execute "C:\ProjectS\ai-knowledge-assistant\run_collector.bat"
$trigger = New-ScheduledTaskTrigger -Daily -At 5:00AM
Register-ScheduledTask -TaskName "AI-Knowledge-Collector" -Action $action -Trigger $trigger -Description "매일 새벽 5시 AI 정보 수집·요약"
```
Expected: `AI-Knowledge-Collector` 작업 등록됨

- [ ] **Step 4: 커밋**

```bash
git add run_collector.bat .gitignore
git commit -m "chore(collector): daily 5AM schedule via Task Scheduler"
```

---

## Task 11: 첫 실제 실행 + 검증 + 푸시

- [ ] **Step 1: GEMINI_API_KEY 환경변수 확인** (요약 호출에 필요)

Run:
```bash
.venv/Scripts/python -c "import os; print('OK' if os.environ.get('GEMINI_API_KEY') else 'MISSING')"
```
Expected: `OK` (없으면 `setx GEMINI_API_KEY <키>` 후 새 셸)

- [ ] **Step 2: 수동 1회 실행**

Run:
```bash
.venv/Scripts/python -m collector run
```
Expected: `[done] N건 → notes/daily/2026-06-27.md`

- [ ] **Step 3: 결과 확인** — `notes/daily/<오늘>.md` 열어 출처별 한국어 요약이 들어있는지 본다. 같은 명령 재실행 시 새 항목 0건(중복 안 됨)인지 확인.

- [ ] **Step 4: 커밋 + 푸시**

```bash
git add notes/daily
git commit -m "feat: first daily AI digest"
git push origin master
```

---

## 완료 정의 (1단계)

- `python -m collector run`이 출처별 새 글을 한국어 요약본 1장(`notes/daily/<날짜>.md`)으로 만든다.
- 재실행해도 중복이 안 생긴다(상태추적).
- 작업 스케줄러가 매일 05:00에 자동 실행한다.
- 출처 추가/삭제 = `sources.yaml` 한 곳 수정.
