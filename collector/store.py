import json, os, dataclasses
from dataclasses import asdict
from typing import List, Set
from .models import Item

_FIELDS = {f.name for f in dataclasses.fields(Item)}

def _stored_ids(path: str) -> Set[str]:
    """이미 저장된 항목 id 집합 (깨진 줄은 무시)."""
    if not os.path.exists(path):
        return set()
    ids: Set[str] = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ids.add(json.loads(line).get("id"))
            except (json.JSONDecodeError, AttributeError):
                continue
    return ids

def append_items(items: List[Item], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    seen = _stored_ids(path)   # 크래시 후 재실행 시 같은 항목 중복 저장 방지
    with open(path, "a", encoding="utf-8") as f:
        for it in items:
            if it.id in seen:
                continue
            seen.add(it.id)
            f.write(json.dumps(asdict(it), ensure_ascii=False) + "\n")

def load_items(path: str) -> List[Item]:
    if not os.path.exists(path):
        return []
    out: List[Item] = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                out.append(Item(**{k: v for k, v in data.items() if k in _FIELDS}))
            except (json.JSONDecodeError, TypeError) as e:
                # partial write 등으로 깨진 줄 하나 때문에 cron이 영구히 죽지 않게 skip
                print(f"[warn] {path}:{lineno} 깨진 줄 skip: {str(e)[:60]}")
    return out
