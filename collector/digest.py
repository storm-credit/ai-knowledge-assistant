import os
from collections import defaultdict
from typing import List
from .models import Item
from .mdutil import safe_md_link

def render_markdown(items: List[Item], date: str) -> str:
    lines = [f"# {date} AI 요약", "", f"> 총 {len(items)}건", ""]
    by_source = defaultdict(list)
    for it in items:
        by_source[it.source_name].append(it)
    for source, group in by_source.items():
        lines.append(f"## {source}")
        for it in group:
            lines.append(f"### {safe_md_link(it.title, it.link)}")
            lines.append(it.summary or "(요약 없음)")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"

def write_digest(items: List[Item], date: str, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{date}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_markdown(items, date))
    return path
