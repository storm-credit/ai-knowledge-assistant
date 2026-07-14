from typing import Callable, List
from .store import load_items
from .state import StateStore
from .topics import TopicStore, write_pages, write_index
from .classify import classify_item
from .wikisynth import synthesize_structure, SYNTH_WINDOW

# 주제당 항목 상한. 테마는 최근 25건(SYNTH_WINDOW)으로 만들어지므로 50 유지 시
# 테마에 남을 최근 항목은 보존되고 오래된 단신만 자동 정리된다.
TOPIC_MAX_ITEMS = 50

def run_wiki(items_store: str = "state/items.jsonl",
             classified_state: str = "state/classified.json",
             topics_path: str = "state/topics.json",
             out_dir: str = "notes/topics",
             classify: Callable = classify_item,
             synthesize: Callable = synthesize_structure,
             resynth_threshold: int = 5) -> List[str]:
    items = load_items(items_store)
    seen = StateStore(classified_state)
    store = TopicStore(topics_path)

    new = [it for it in items if seen.is_new(it.id)]
    for it in new:
        try:
            # 파이프라인 결합 호출로 이미 분류된 항목은 LLM 재호출 없이 재사용
            topics = it.categories if it.categories else classify(it)
        except Exception as e:
            print(f"[skip] 분류 실패 {it.title[:30]}: {e}")
            continue
        if not topics:
            # 빈 분류 결과를 seen 처리하면 항목이 어떤 주제에도 없이 영구 유실됨
            print(f"[retry-later] 분류 결과 없음 {it.title[:30]} — 다음 실행에 재시도")
            continue
        for tp in topics:
            store.add_item(tp, it)
        seen.mark_seen(it.id)

    # 합성/렌더 전에 주제별 상한 적용: 오래된 단신만 자르고 테마용 최근 항목은 보존.
    # topics.json의 주제별 items만 자른다(items.jsonl 원본은 그대로).
    for tp in store.topic_names():
        store.prune_topic(tp, max_items=TOPIC_MAX_ITEMS)

    for tp in store.topic_names():
        needs = store.needs_resynth(tp, resynth_threshold)
        if not needs and store.data[tp].get("synthesized"):
            continue
        if not needs and store.synth_backoff(tp):
            continue   # 2회 연속 빈 합성 → 새 항목이 threshold만큼 쌓일 때까지 스킵
        try:
            # 응답의 번호 → id 매핑이 윈도우 기준이 되도록 같은 슬라이스를 양쪽에 사용
            window = store.data[tp]["items"][-SYNTH_WINDOW:]
            r = synthesize(tp, window)
            if r.get("overview") or r.get("themes"):
                store.set_structure(tp, r["overview"], r["themes"], r["orphans"],
                                    r["related"], window=window)
            else:
                # 기존 데이터 보존, synthesized 미표시 + 실패 기록 (백오프용)
                store.record_synth_failure(tp)
        except Exception as e:
            print(f"[skip] 구조 합성 실패 {tp}: {e}")

    store.save()
    seen.save()
    paths = write_pages(store, out_dir)
    write_index(store, out_dir)
    print(f"[wiki] {len(new)}건 분류, {len(paths)}개 주제 페이지 → {out_dir}")
    return paths
