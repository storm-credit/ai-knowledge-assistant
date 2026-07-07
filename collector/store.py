import json, os, dataclasses
from dataclasses import asdict
from datetime import date, timedelta
from typing import List, Optional, Set
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

def load_items(path: str, limit: Optional[int] = None) -> List[Item]:
    # limit이 주어지면 파일 끝에서부터 마지막 limit줄만 로드(최신 항목이 뒤에 append됨).
    # 기본 None은 기존과 동일하게 전량 로드. 수백~수천 줄 규모라 전체 read 후 슬라이스로 충분.
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    if limit is not None:
        lines = lines[-limit:]
    out: List[Item] = []
    for lineno, line in enumerate(lines, 1):
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

def _pub_date(s) -> Optional[date]:
    """published 문자열 앞 10자를 날짜로 파싱. 실패하면 None."""
    try:
        return date.fromisoformat(str(s)[:10])
    except (ValueError, TypeError):
        return None

def archive_old_items(path: str, keep_days: int = 90, today: Optional[date] = None,
                      archive_dir: Optional[str] = None) -> int:
    """published 기준 keep_days보다 오래된 항목을 items-archive.jsonl로 옮기고
    원본에는 최근 것만 남긴다. 파괴적이므로 명시 호출 시에만 동작(자동 실행 금지).
    - 원본이 없으면 no-op. 옮길 게 없으면 원본을 재작성하지 않는다.
    - published가 없거나 파싱 불가한 항목, 깨진 줄은 판단 불가 → 원본에 그대로 보존.
    반환값: 아카이브로 옮긴 항목 수."""
    if not os.path.exists(path):
        return 0
    if today is None:
        today = date.today()
    cutoff = today - timedelta(days=keep_days)
    keep_lines: List[str] = []
    archive_lines: List[str] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                data = json.loads(s)
            except json.JSONDecodeError:
                keep_lines.append(s)   # 깨진 줄은 손실 없이 원본에 보존
                continue
            pub = _pub_date(data.get("published") or "")
            if pub is not None and pub < cutoff:
                archive_lines.append(s)
            else:
                keep_lines.append(s)   # published 없거나 최근이면 유지
    if not archive_lines:
        return 0                        # 옮길 게 없으면 원본 그대로 둔다
    arc_dir = archive_dir or os.path.dirname(path) or "."
    os.makedirs(arc_dir, exist_ok=True)
    arc_path = os.path.join(arc_dir, "items-archive.jsonl")
    with open(arc_path, "a", encoding="utf-8") as f:
        for s in archive_lines:
            f.write(s + "\n")
    with open(path, "w", encoding="utf-8") as f:
        for s in keep_lines:
            f.write(s + "\n")
    return len(archive_lines)
