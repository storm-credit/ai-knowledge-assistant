import json, os, time
from typing import Set

# ── 동시 실행 락 (#18) ────────────────────────────────────────────────────
LOCK_PATH = "state/.lock"
LOCK_MAX_AGE = 2 * 60 * 60   # 죽은 실행이 남긴 락은 2시간 후 낡은 것으로 간주

def acquire_lock(path: str = LOCK_PATH, max_age: float = LOCK_MAX_AGE) -> bool:
    """실행 락 획득. 유효한 락이 이미 있으면 False.
    mtime이 max_age 이상 과거인 낡은 락은 무시하고 진행(갱신)."""
    if os.path.exists(path):
        try:
            fresh = time.time() - os.path.getmtime(path) < max_age
        except OSError:
            fresh = False   # 확인 중 사라짐 → 낡은 락 취급
        if fresh:
            return False
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    return True

def release_lock(path: str = LOCK_PATH) -> None:
    try:
        os.remove(path)
    except OSError:
        pass

def load_json_or_backup(path: str, default):
    """JSON 로드. corrupt면 원본을 .bak로 백업하고 default 반환 (cron 영구 사망 방지)."""
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except ValueError as e:   # JSONDecodeError·UnicodeDecodeError 포함
        bak = path + ".bak"
        os.replace(path, bak)
        print(f"[warn] {path} corrupt → {bak}로 백업 후 빈 상태로 시작: {str(e)[:60]}")
        return default

class StateStore:
    def __init__(self, path: str):
        self.path = path
        data = load_json_or_backup(path, {})
        if not isinstance(data, dict):   # 형식이 다른 것도 corrupt 취급
            data = {}
        self._seen: Set[str] = set(data.get("seen", []))

    def is_new(self, item_id: str) -> bool:
        return item_id not in self._seen

    def mark_seen(self, item_id: str) -> None:
        self._seen.add(item_id)

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"seen": sorted(self._seen)}, f, ensure_ascii=False, indent=2)
