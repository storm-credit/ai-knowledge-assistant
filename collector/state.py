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
