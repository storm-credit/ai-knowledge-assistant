from typing import Callable, List
from .config import SourcesConfig, Source
from .models import Item
from .state import StateStore
from .feeds import fetch_feed
from .enrich import enrich_youtube
from .summarize import summarize_item
from .digest import write_digest

def run(cfg: SourcesConfig, state: StateStore, out_dir: str, date: str,
        fetch: Callable[[Source], List[Item]] = fetch_feed,
        enrich: Callable[[Item], Item] = enrich_youtube,
        summarize: Callable[[Item], Item] = summarize_item) -> str:
    new_items: List[Item] = []
    for src in (cfg.youtube + cfg.newsletters):
        try:
            items = fetch(src)
        except Exception as e:
            print(f"[skip] {src.name} 수집 실패: {e}")   # 개별 실패 격리
            continue
        for it in items:
            if not state.is_new(it.id):
                continue
            if it.source_type == "youtube":
                it = enrich(it)
            try:
                it = summarize(it)
            except Exception as e:
                it.summary = f"(요약 실패: {e})"
            new_items.append(it)
            state.mark_seen(it.id)

    path = write_digest(new_items, date=date, out_dir=out_dir)
    state.save()
    print(f"[done] {len(new_items)}건 → {path}")
    return path
