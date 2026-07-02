import os
import time
from typing import Callable, List
from .config import SourcesConfig, Source
from .models import Item
from .state import StateStore
from .feeds import fetch_feed
from .enrich import enrich_youtube
from .llm import QuotaExhausted
from .summarize import batch_summarize
from .digest import write_digest
from .store import append_items

def run(cfg: SourcesConfig, state: StateStore, out_dir: str, date: str,
        fetch: Callable[[Source], List[Item]] = fetch_feed,
        enrich: Callable[[Item], Item] = enrich_youtube,
        summarize: Callable[[Item], Item] = None,
        limit_per_feed: int = 5,
        sleep: Callable[[float], None] = time.sleep,
        throttle_seconds: float = 5.0,
        items_store: str = "state/items.jsonl") -> str:
    # 1) 소스 순회하며 신규 항목 수집 (enrich까지만, 요약은 뒤에서 일괄)
    pending: List[Item] = []
    for src in (cfg.youtube + cfg.newsletters):
        try:
            items = fetch(src)
        except Exception as e:
            print(f"[skip] {src.name} 수집 실패: {e}")   # 개별 실패 격리
            continue
        for it in items[:limit_per_feed]:   # 최신 N개만 (dedup 전에 적용)
            if not state.is_new(it.id):
                continue
            it.learning = src.learning   # 학습형 출처 여부를 항목에 전파
            if it.source_type == "youtube":
                it = enrich(it)
            pending.append(it)

    # 2) 요약: 주입 시 항목당 1콜(테스트 호환), 미주입(실제 cron)이면 배치 요약.
    #    성공분은 그 자리에서 items.jsonl+seen에 영속화 — 이후 크래시에도 요약 콜이 증발하지 않음.
    new_items: List[Item] = []
    if summarize is not None:
        for it in pending:
            try:
                it = summarize(it)
            except Exception as e:
                # 요약 실패(주로 무료 쿼터 초과)는 seen 표시 안 함 → 다음 실행 때 자동 재시도
                print(f"[retry-later] {it.title[:30]} 요약 실패: {str(e)[:60]}")
                continue
            sleep(throttle_seconds)   # 요약 성공 후에만 throttle
            append_items([it], items_store)   # 성공 즉시 영속화 (크래시 대비)
            state.mark_seen(it.id)
            state.save()
            new_items.append(it)
    elif pending:
        try:
            done = batch_summarize(pending, sleep=sleep,
                                   throttle_seconds=throttle_seconds)
        except QuotaExhausted as e:
            # 도중 쿼터 소진 → 예외 전에 요약이 채워진 항목만 성공으로 회수
            print(f"[retry-later] 쿼터 소진, 남은 항목은 다음 실행에: {str(e)[:60]}")
            done = [it for it in pending if it.summary]
        if done:
            append_items(done, items_store)   # 성공분 즉시 영속화 (크래시 대비)
        for it in done:   # 실패 항목은 seen 미표시 → 다음 실행 때 자동 재시도
            state.mark_seen(it.id)
            new_items.append(it)
        state.save()

    if new_items:
        path = write_digest(new_items, date=date, out_dir=out_dir)
    else:
        # 새 항목 0건이면 기존 다이제스트를 덮어쓰지 않음
        path = os.path.join(out_dir, f"{date}.md")
        print("[skip] 새 항목 없음 — 기존 다이제스트 유지")
    state.save()
    print(f"[done] {len(new_items)}건 → {path}")
    return path
