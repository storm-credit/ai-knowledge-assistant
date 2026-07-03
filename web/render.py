"""Pure rendering helpers for the web viewer.

Turns the Obsidian-flavoured markdown in ``notes/topics`` and ``notes/daily``
into HTML the Flask layer can drop into a template. Kept free of Flask so it
stays unit-testable, matching the ``collector`` package's split of pure logic
from I/O glue.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import quote

import markdown as _md
import nh3

# sanitize 허용목록: nh3 기본값 + 렌더가 쓰는 class(콜아웃·기사 카드·코드 언어)와 헤딩 id
_ALLOWED_ATTRIBUTES = {**nh3.ALLOWED_ATTRIBUTES, "*": {"class"}}
for _h in ("h1", "h2", "h3"):
    _ALLOWED_ATTRIBUTES[_h] = _ALLOWED_ATTRIBUTES.get(_h, set()) | {"id"}

ROOT = Path(__file__).resolve().parent.parent
TOPICS_DIR = ROOT / "notes" / "topics"
DAILY_DIR = ROOT / "notes" / "daily"

_TOC_NAME = "00-목차"
_WIKILINK = re.compile(r"\[\[([^\]]+?)\]\]")
_TOC_LINE = re.compile(r"^-\s*\[\[(?P<name>.+?)\]\]\s*[—-]\s*(?P<body>.+)$")
_CALLOUT_HEAD = re.compile(r"^>\s*\[!(?P<kind>\w+)\]\s*(?P<title>.*)$")
_DAILY_FILE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# emoji shown on abstract-style callouts; falls back to a neutral marker
_CALLOUT_ICON = {"abstract": "📄", "note": "📝", "info": "ℹ️", "tip": "💡"}


@dataclass
class TopicCard:
    name: str
    count: str  # free-form label, e.g. "42건 · 7개 출처"


@dataclass
class DailyEntry:
    date: str
    title: str


def _safe_name(name: str) -> Optional[str]:
    """Reject anything that could escape the notes dir (path traversal)."""
    if not name or "/" in name or "\\" in name or ".." in name:
        return None
    return name


_FENCE = re.compile(r"^\s*(```|~~~)")
_INLINE_CODE = re.compile(r"(`+[^`]*?`+)")


def _apply_outside_code(text: str, fn, skip_quotes: bool = False) -> str:
    """코드펜스(```)·인라인 코드(`…`) 구간은 건너뛰고 fn을 적용한다.

    ``skip_quotes=True``면 인용/콜아웃(``>``) 줄도 건너뛴다 — 콜아웃 본문은
    이후 HTML 이스케이프되므로 마크다운 문법을 넣어봐야 깨져 보이기 때문.
    """
    out: List[str] = []
    in_fence = False
    for line in text.split("\n"):
        if _FENCE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence or (skip_quotes and line.lstrip().startswith(">")):
            out.append(line)
            continue
        # 인라인 코드를 캡처 그룹으로 split → 홀수 인덱스가 코드 구간
        parts = _INLINE_CODE.split(line)
        out.append("".join(p if i % 2 else fn(p) for i, p in enumerate(parts)))
    return "\n".join(out)


def _replace_wikilinks(text: str) -> str:
    """``[[Topic]]`` -> markdown link into the topic route (코드 구간 제외)."""
    sub = lambda seg: _WIKILINK.sub(
        lambda m: f"[{m.group(1)}](/topic/{quote(m.group(1))})", seg
    )
    return _apply_outside_code(text, sub)


# 맨몸 URL: 이미 링크 문법 안에 있는 것(`(`, `[`, `<` 뒤)은 제외
_BARE_URL = re.compile(r'(?<![(<\[])\bhttps?://[^\s<>"\')\]]+')


def _autolink_urls(text: str) -> str:
    """데일리 요약의 맨몸 URL을 마크다운 링크로 (코드·인용 구간 제외)."""

    def link(m: re.Match) -> str:
        url = m.group(0).rstrip(".,;:!?")   # 문장부호가 URL에 붙는 것 방지
        trail = m.group(0)[len(url):]
        return f"[{url}]({url}){trail}"

    return _apply_outside_code(text, lambda seg: _BARE_URL.sub(link, seg), skip_quotes=True)


def _transform_callouts(text: str) -> str:
    """Convert Obsidian callout blocks into styled raw-HTML divs.

    A callout is a run of ``>`` lines whose first line is ``> [!kind] title``.
    Bodies are plain prose here, so they are HTML-escaped and joined with
    ``<br>`` rather than re-parsed as markdown.
    """
    lines = text.split("\n")
    out: List[str] = []
    i = 0
    while i < len(lines):
        head = _CALLOUT_HEAD.match(lines[i])
        if not head:
            out.append(lines[i])
            i += 1
            continue
        kind = head.group("kind").lower()
        title = head.group("title").strip()
        body: List[str] = []
        i += 1
        while i < len(lines) and lines[i].startswith(">"):
            body.append(lines[i].lstrip(">").strip())
            i += 1
        icon = _CALLOUT_ICON.get(kind, "📌")
        body_html = "<br>".join(html.escape(b) for b in body if b)
        title_html = html.escape(title) if title else kind
        out.append(
            f'<div class="callout callout-{html.escape(kind)}">'
            f'<div class="callout-title">{icon} {title_html}</div>'
            f'<div class="callout-body">{body_html}</div></div>'
        )
    return "\n".join(out)


_HEADING = re.compile(r"<(h2|h3)\b")


def _wrap_articles(html: str) -> str:
    """Wrap each ``<h3>`` article (title + byline + summary) in a card div.

    Each ``### [title](url)`` becomes a distinct visual block that closes at
    the next ``<h3>``/``<h2>``. Theme headings (``<h2>``) and their intro text,
    plus non-article sections (단신 목록, 메모, 관련 주제), stay uncarded.
    """
    tags = [(m.start(), m.group(1)) for m in _HEADING.finditer(html)]
    if not tags:
        return html
    bounds = [t[0] for t in tags] + [len(html)]
    out = [html[: bounds[0]]]
    open_article = False
    for i, (pos, tag) in enumerate(tags):
        seg = html[pos : bounds[i + 1]]
        if tag == "h3":
            if open_article:
                out.append("</div>")
            # 학습형 기사(굵은 '핵심 개념' 라벨 포함)는 뱃지용 클래스 추가
            cls = (
                "article article--learning"
                if "<strong>핵심 개념</strong>" in seg
                else "article"
            )
            out.append(f'<div class="{cls}">')
            out.append(seg)
            open_article = True
        else:  # h2: close any open article, leave the theme section uncarded
            if open_article:
                out.append("</div>")
                open_article = False
            out.append(seg)
    if open_article:
        out.append("</div>")
    return "".join(out)


def render_markdown(text: str) -> str:
    """Obsidian markdown -> HTML (wikilinks + callouts handled)."""
    text = _replace_wikilinks(text)
    text = _autolink_urls(text)
    text = _transform_callouts(text)
    html = _md.markdown(text, extensions=["extra", "sane_lists"])
    html = _wrap_articles(html)
    # 피드·LLM 요약에 섞여 들어온 raw HTML(<script>, onerror 등)을 허용목록으로 차단
    return nh3.clean(html, attributes=_ALLOWED_ATTRIBUTES, link_rel=None)


def _split_title(text: str) -> Tuple[str, str]:
    """Peel the leading ``# Title`` line off; return (title, remaining body)."""
    lines = text.split("\n")
    if lines and lines[0].startswith("# "):
        return lines[0][2:].strip(), "\n".join(lines[1:]).lstrip("\n")
    return "", text


def list_topics(topics_dir: Path = TOPICS_DIR) -> List[TopicCard]:
    """Topics in 목차 order; falls back to scanning the directory."""
    toc = topics_dir / f"{_TOC_NAME}.md"
    cards: List[TopicCard] = []
    if toc.exists():
        for line in toc.read_text(encoding="utf-8").split("\n"):
            m = _TOC_LINE.match(line.strip())
            if m:
                cards.append(TopicCard(name=m.group("name"), count=m.group("body").strip()))
    if cards:
        return cards
    for path in sorted(topics_dir.glob("*.md")):
        if path.stem == _TOC_NAME:
            continue
        cards.append(TopicCard(name=path.stem, count=""))
    return cards


def load_topic(name: str, topics_dir: Path = TOPICS_DIR) -> Optional[Tuple[str, str]]:
    """Return (title, html) for a topic, or None if missing/unsafe."""
    safe = _safe_name(name)
    if safe is None:
        return None
    path = topics_dir / f"{safe}.md"
    if not path.exists():
        return None
    title, body = _split_title(path.read_text(encoding="utf-8"))
    return title or safe, render_markdown(body)


LEARN_DIR = ROOT / "notes" / "learn"


@dataclass
class LearnEntry:
    name: str    # 파일명(stem) = 라우트 키
    title: str


def list_learn_notes(learn_dir: Path = LEARN_DIR) -> List[LearnEntry]:
    """적용형 학습 노트 목록, 최근 생성(mtime) 순."""
    if not learn_dir.exists():
        return []
    entries: List[LearnEntry] = []
    for path in sorted(learn_dir.glob("*.md"),
                       key=lambda p: p.stat().st_mtime, reverse=True):
        title, _ = _split_title(path.read_text(encoding="utf-8-sig"))
        entries.append(LearnEntry(name=path.stem, title=title or path.stem))
    return entries


def load_learn_note(name: str, learn_dir: Path = LEARN_DIR) -> Optional[Tuple[str, str]]:
    """Return (title, html) for a learn note, or None if missing/unsafe."""
    safe = _safe_name(name)
    if safe is None:
        return None
    path = learn_dir / f"{safe}.md"
    if not path.exists():
        return None
    title, body = _split_title(path.read_text(encoding="utf-8-sig"))
    return title or safe, render_markdown(body)


def list_dailies(daily_dir: Path = DAILY_DIR) -> List[DailyEntry]:
    """Daily notes, newest first."""
    entries: List[DailyEntry] = []
    for path in sorted(daily_dir.glob("*.md"), reverse=True):
        if not _DAILY_FILE.match(path.stem):
            continue
        title, _ = _split_title(path.read_text(encoding="utf-8"))
        entries.append(DailyEntry(date=path.stem, title=title or path.stem))
    return entries


def load_daily(date: str, daily_dir: Path = DAILY_DIR) -> Optional[Tuple[str, str]]:
    """Return (title, html) for a daily note, or None if missing/unsafe."""
    if not _DAILY_FILE.match(date):
        return None
    path = daily_dir / f"{date}.md"
    if not path.exists():
        return None
    title, body = _split_title(path.read_text(encoding="utf-8"))
    return title or date, render_markdown(body)
