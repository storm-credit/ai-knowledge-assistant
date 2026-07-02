import os
from collections import defaultdict, OrderedDict
from typing import List
from .models import Item
from .mdutil import safe_md_link

def _item_heading(it: Item) -> str:
    return f"### {safe_md_link(it.title, it.link)}"

def render_markdown(items: List[Item], date: str) -> str:
    lines = [f"# {date} AI 요약", "", f"> 총 {len(items)}건", ""]
    by_source = defaultdict(list)
    for it in items:
        by_source[it.source_name].append(it)
    for source, group in by_source.items():
        lines.append(f"## {source}")
        for it in group:
            lines.append(_item_heading(it))
            lines.append(it.summary or "(요약 없음)")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"

def _parse_sections(text: str):
    """기존 다이제스트를 출처별 항목 블록으로 파싱. (섹션, 항목 헤딩 집합) 반환."""
    sections: "OrderedDict[str, list]" = OrderedDict()   # 출처 -> [항목 블록(줄 리스트)]
    headings = set()   # 제목+링크 헤딩 라인 기준 dedup 키
    source = None
    block = None
    for line in text.splitlines():
        if line.startswith("### ") and source is not None:
            block = [line]
            sections[source].append(block)
            headings.add(line.rstrip())
        elif line.startswith("## "):
            source = line[3:].strip()
            sections.setdefault(source, [])
            block = None
        elif block is not None:
            block.append(line)
    return sections, headings

def merge_markdown(existing: str, items: List[Item], date: str) -> str:
    """당일 재실행 병합: 기존 항목 유지 + 신규 항목만 해당 출처 섹션에 추가."""
    sections, headings = _parse_sections(existing)
    for it in items:
        head = _item_heading(it)
        if head in headings:   # 이미 있는 항목(제목+링크 동일)은 건너뜀
            continue
        headings.add(head)
        sections.setdefault(it.source_name, []).append(
            [head, it.summary or "(요약 없음)", ""])
    total = sum(len(blocks) for blocks in sections.values())
    lines = [f"# {date} AI 요약", "", f"> 총 {total}건", ""]
    for source, blocks in sections.items():
        lines.append(f"## {source}")
        for block in blocks:
            lines.extend(block)
    return "\n".join(lines).rstrip() + "\n"

def write_digest(items: List[Item], date: str, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{date}.md")
    if os.path.exists(path):
        # 당일 재실행(쿼터 초과 후 재시도) → 아침 수집분을 유지하며 병합
        with open(path, encoding="utf-8") as f:
            content = merge_markdown(f.read(), items, date)
    else:
        content = render_markdown(items, date)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path
