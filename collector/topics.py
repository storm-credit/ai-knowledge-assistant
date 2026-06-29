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

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)


import re as _re

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

def write_pages(store: "TopicStore", out_dir: str) -> list:
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    current = set()
    for topic, t in store.data.items():
        safe = _re.sub(r'[\\/:*?"<>|]', "_", topic).strip() or "untitled"
        fname = f"{safe}.md"
        current.add(fname)
        p = os.path.join(out_dir, fname)
        with open(p, "w", encoding="utf-8") as f:
            f.write(render_page(topic, t))
        paths.append(p)
    # 스테일 정리: 현재 주제도, 목차(00-목차.md)도 아닌 .md 파일 삭제 (분류 체계 바뀔 때 고아 파일 방지)
    for fn in os.listdir(out_dir):
        if fn.endswith(".md") and fn not in current and fn != "00-목차.md":
            try:
                os.remove(os.path.join(out_dir, fn))
            except OSError:
                pass
    return paths

def render_index(store: "TopicStore") -> str:
    lines = ["# 📚 목차", ""]
    topics = sorted(store.data.items(), key=lambda kv: len(kv[1]["items"]), reverse=True)
    for topic, t in topics:
        lines.append(f"- [[{topic}]] — {len(t['items'])}건 · {len(t['sources'])}개 출처")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"

def write_index(store: "TopicStore", out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, "00-목차.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write(render_index(store))
    return p
