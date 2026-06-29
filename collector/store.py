import json, os, dataclasses
from dataclasses import asdict
from typing import List
from .models import Item

_FIELDS = {f.name for f in dataclasses.fields(Item)}

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
                out.append(Item(**{k: v for k, v in json.loads(line).items() if k in _FIELDS}))
    return out
