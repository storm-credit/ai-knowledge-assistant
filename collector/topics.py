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
