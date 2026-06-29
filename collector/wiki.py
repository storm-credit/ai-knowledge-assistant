from typing import Callable, List
from .store import load_items
from .state import StateStore
from .topics import TopicStore, write_pages, write_index
from .classify import classify_item
from .wikisynth import synthesize_structure

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
    known = store.topic_names()

    new = [it for it in items if seen.is_new(it.id)]
    for it in new:
        try:
            # 파이프라인 결합 호출로 이미 분류된 항목은 LLM 재호출 없이 재사용
            topics = it.categories if it.categories else classify(it, known)
        except Exception as e:
            print(f"[skip] 분류 실패 {it.title[:30]}: {e}")
            continue
        for tp in topics:
            store.add_item(tp, it)
            if tp not in known:
                known.append(tp)
        seen.mark_seen(it.id)

    for tp in store.topic_names():
        if store.needs_resynth(tp, resynth_threshold) or not store.data[tp].get("synthesized"):
            try:
                r = synthesize(tp, store.data[tp]["items"])
                store.set_structure(tp, r["overview"], r["themes"], r["orphans"], r["related"])
            except Exception as e:
                print(f"[skip] 구조 합성 실패 {tp}: {e}")

    store.save()
    seen.save()
    paths = write_pages(store, out_dir)
    write_index(store, out_dir)
    print(f"[wiki] {len(new)}건 분류, {len(paths)}개 주제 페이지 → {out_dir}")
    return paths
