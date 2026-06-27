import os
import time
from typing import Callable, List
from .config import SourcesConfig, Source
from .models import Item
from .state import StateStore
from .feeds import fetch_feed
from .enrich import enrich_youtube
from .summarize import summarize_item, summarize_and_classify
from .digest import write_digest
from .store import append_items

def run(cfg: SourcesConfig, state: StateStore, out_dir: str, date: str,
        fetch: Callable[[Source], List[Item]] = fetch_feed,
        enrich: Callable[[Item], Item] = enrich_youtube,
        summarize: Callable[[Item], Item] = summarize_and_classify,
        limit_per_feed: int = 5,
        sleep: Callable[[float], None] = time.sleep,
        throttle_seconds: float = 5.0,
        items_store: str = "state/items.jsonl") -> str:
    new_items: List[Item] = []
    for src in (cfg.youtube + cfg.newsletters):
        try:
            items = fetch(src)
        except Exception as e:
            print(f"[skip] {src.name} 수집 실패: {e}")   # 개별 실패 격리
            continue
        for it in items[:limit_per_feed]:   # 최신 N개만 (dedup 전에 적용)
            if not state.is_new(it.id):
                continue
            if it.source_type == "youtube":
                it = enrich(it)
            try:
                it = summarize(it)
            except Exception as e:
                # 요약 실패(주로 무료 쿼터 초과)는 seen 표시 안 함 → 다음 실행 때 자동 재시도
                print(f"[retry-later] {it.title[:30]} 요약 실패: {str(e)[:60]}")
                continue
            sleep(throttle_seconds)   # 요약 성공 후에만 throttle
            new_items.append(it)
            state.mark_seen(it.id)

    if new_items:
        append_items(new_items, items_store)
        path = write_digest(new_items, date=date, out_dir=out_dir)
    else:
        # 새 항목 0건이면 기존 다이제스트를 덮어쓰지 않음
        path = os.path.join(out_dir, f"{date}.md")
        print("[skip] 새 항목 없음 — 기존 다이제스트 유지")
    state.save()
    print(f"[done] {len(new_items)}건 → {path}")
    return path
