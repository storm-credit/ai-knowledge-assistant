from collector.models import Item
from collector.store import append_items
from collector.wiki import run_wiki

def mk(id, title, categories=None): return Item(source_name="조코딩", source_type="x", id=id,
                               title=title, link="http://"+id, published="2026-06-27", summary="요약",
                               categories=categories or [])

def test_run_wiki_classifies_and_writes(tmp_path):
    items_store = str(tmp_path/"items.jsonl")
    append_items([mk("a","에이전트 글"), mk("b","Claude 글")], items_store)

    def fake_classify(item):
        return ["AI 에이전트"] if "에이전트" in item.title else ["Claude"]
    def fake_synth(topic, items):
        return {"overview": f"{topic} 개요", "themes": [], "orphans": [], "related": ["기타"]}

    paths = run_wiki(items_store=items_store,
                     classified_state=str(tmp_path/"classified.json"),
                     topics_path=str(tmp_path/"topics.json"),
                     out_dir=str(tmp_path/"topics"),
                     classify=fake_classify, synthesize=fake_synth, resynth_threshold=1)
    names = [p.split("\\")[-1].split("/")[-1] for p in paths]
    assert "AI 에이전트.md" in names and "Claude.md" in names

    # 재실행 시 이미 분류된 건 건너뜀 (새 0건)
    paths2 = run_wiki(items_store=items_store,
                      classified_state=str(tmp_path/"classified.json"),
                      topics_path=str(tmp_path/"topics.json"),
                      out_dir=str(tmp_path/"topics"),
                      classify=fake_classify, synthesize=fake_synth, resynth_threshold=1)
    # 페이지는 여전히 렌더되지만, items.jsonl의 두 항목은 재분류 안 됨
    import json
    cl = json.load(open(str(tmp_path/"classified.json"), encoding="utf-8"))
    assert set(cl["seen"]) == {"a", "b"}

def test_run_wiki_writes_index(tmp_path):
    items_store = str(tmp_path/"items.jsonl")
    append_items([mk("a","에이전트 글"), mk("b","Claude 글")], items_store)

    def fake_classify(item):
        return ["AI 에이전트"] if "에이전트" in item.title else ["Claude"]
    def fake_synth(topic, items):
        return {"overview": f"{topic} 개요", "themes": [], "orphans": [], "related": ["기타"]}

    run_wiki(items_store=items_store,
             classified_state=str(tmp_path/"classified.json"),
             topics_path=str(tmp_path/"topics.json"),
             out_dir=str(tmp_path/"topics"),
             classify=fake_classify, synthesize=fake_synth, resynth_threshold=1)

    import os
    index = tmp_path/"topics"/"00-목차.md"
    assert os.path.exists(str(index))
    assert "# 📚 목차" in index.read_text(encoding="utf-8")

def test_run_wiki_uses_preclassified_categories_without_calling_classify(tmp_path):
    items_store = str(tmp_path/"items.jsonl")
    # 이미 카테고리가 채워진 항목 (파이프라인 결합 호출 결과)
    append_items([mk("a", "어떤 글", categories=["Claude"])], items_store)

    calls = {"n": 0}
    def fake_classify(item):
        calls["n"] += 1
        raise AssertionError("미리 분류된 항목엔 classify 호출 금지")
    def fake_synth(topic, items):
        return {"overview": f"{topic} 개요", "themes": [], "orphans": [], "related": []}

    paths = run_wiki(items_store=items_store,
                     classified_state=str(tmp_path/"classified.json"),
                     topics_path=str(tmp_path/"topics.json"),
                     out_dir=str(tmp_path/"topics"),
                     classify=fake_classify, synthesize=fake_synth, resynth_threshold=1)
    assert calls["n"] == 0                       # classify 미호출 → LLM 0콜
    names = [p.split("\\")[-1].split("/")[-1] for p in paths]
    assert "Claude.md" in names                  # 항목이 Claude 주제로 들어감


def test_run_wiki_builds_themes(tmp_path):
    from collector.models import Item
    from collector.store import append_items
    from collector.wiki import run_wiki
    from collector.topics import TopicStore
    items_store = str(tmp_path/"items.jsonl")
    append_items([Item(source_name="s", source_type="x", id=f"id{i}", title=f"T{i}",
                       link=f"http://{i}", published="2026-06-29", summary=f"s{i}",
                       categories=["AI"]) for i in (1,2)], items_store)
    def fake_struct(topic, items):
        return {"overview":"개요","themes":[{"name":"테마","intro":"정리","indexes":[1]}],
                "orphans":[2],"related":["Claude"]}
    run_wiki(items_store=items_store, classified_state=str(tmp_path/"c.json"),
             topics_path=str(tmp_path/"t.json"), out_dir=str(tmp_path/"topics"),
             classify=lambda it: it.categories, synthesize=fake_struct, resynth_threshold=1)
    d = TopicStore(str(tmp_path/"t.json")).data["AI"]
    assert d["themes"][0]["name"] == "테마"
    assert d["themes"][0]["item_ids"] == ["id1"]
    assert d["orphans"] == ["id2"]


def test_run_wiki_empty_synth_does_not_overwrite(tmp_path):
    # 빈 합성 결과가 기존 좋은 데이터를 덮어쓰지 않아야 한다 (Fix 1)
    from collector.models import Item
    from collector.store import append_items
    from collector.wiki import run_wiki
    from collector.topics import TopicStore
    items_store = str(tmp_path/"items.jsonl")
    append_items([Item(source_name="s", source_type="x", id="id1", title="T1",
                       link="http://1", published="2026-06-29", summary="s1",
                       categories=["AI"])], items_store)
    topics_path = str(tmp_path/"t.json")
    # 사전에 좋은 구조를 심어둔다 (synthesized 미표시 → resynth 경로가 돈다)
    pre = TopicStore(topics_path)
    pre.add_item("AI", Item(source_name="s", source_type="x", id="id1", title="T1",
                            link="http://1", published="2026-06-29", summary="s1"))
    pre.data["AI"]["overview"] = "기존 좋은 개요"
    pre.data["AI"]["themes"] = [{"name":"기존테마","intro":"정리","item_ids":["id1"]}]
    pre.data["AI"]["related"] = ["Claude"]
    pre.save()
    def empty_synth(topic, items):
        return {"overview":"", "themes":[], "orphans":[], "related":[]}
    run_wiki(items_store=items_store, classified_state=str(tmp_path/"c.json"),
             topics_path=topics_path, out_dir=str(tmp_path/"topics"),
             classify=lambda it: it.categories, synthesize=empty_synth,
             resynth_threshold=1)
    d = TopicStore(topics_path).data["AI"]
    assert d["overview"] == "기존 좋은 개요"           # 덮어쓰이지 않음
    assert d["themes"][0]["name"] == "기존테마"        # 테마 보존
    assert not d.get("synthesized")                    # synthesized 표시 안 됨 → 다음에 재시도


def test_run_wiki_no_resynth_when_zero_themes(tmp_path):
    # 테마가 0개로 합성돼도 synthesized 플래그가 서므로 다음 실행에서 재합성 안 함 (쿼터 절약)
    from collector.models import Item
    from collector.store import append_items
    from collector.wiki import run_wiki
    items_store = str(tmp_path/"items.jsonl")
    append_items([Item(source_name="s", source_type="x", id="id1", title="T1",
                       link="http://1", published="2026-06-29", summary="s1",
                       categories=["AI"])], items_store)
    calls = {"n": 0}
    def fake_struct(topic, items):
        calls["n"] += 1
        return {"overview":"개요","themes":[],"orphans":[],"related":[]}
    kw = dict(items_store=items_store, classified_state=str(tmp_path/"c.json"),
              topics_path=str(tmp_path/"t.json"), out_dir=str(tmp_path/"topics"),
              classify=lambda it: it.categories, synthesize=fake_struct,
              resynth_threshold=99)   # needs_resynth 비활성
    run_wiki(**kw)
    assert calls["n"] == 1            # 첫 실행에 1회 합성
    run_wiki(**kw)
    assert calls["n"] == 1            # 두 번째 실행에선 재합성 안 함 (플래그 가드)


# ── run_wiki 실패 경로 3종 (카드 F) ──────────────────────────────────────

def _empty_synth(topic, items):
    return {"overview": "", "themes": [], "orphans": [], "related": []}


def test_run_wiki_classify_exception_not_marked_seen(tmp_path):
    # (a) 분류 예외 → seen 미마킹 → 다음 실행에 재시도
    import json
    items_store = str(tmp_path/"items.jsonl")
    append_items([mk("a", "글")], items_store)
    def boom(item):
        raise RuntimeError("LLM down")
    run_wiki(items_store=items_store, classified_state=str(tmp_path/"c.json"),
             topics_path=str(tmp_path/"t.json"), out_dir=str(tmp_path/"topics"),
             classify=boom, synthesize=_empty_synth, resynth_threshold=1)
    cl = json.load(open(str(tmp_path/"c.json"), encoding="utf-8"))
    assert "a" not in cl["seen"]


def test_run_wiki_synth_exception_preserves_structure(tmp_path):
    # (b) 합성 예외 → 기존 overview/themes 보존
    from collector.topics import TopicStore
    items_store = str(tmp_path/"items.jsonl")
    append_items([mk("a", "글", categories=["AI"])], items_store)
    topics_path = str(tmp_path/"t.json")
    pre = TopicStore(topics_path)
    pre.add_item("AI", mk("a", "글"))
    pre.data["AI"]["overview"] = "기존 좋은 개요"
    pre.data["AI"]["themes"] = [{"name": "기존테마", "intro": "정리", "item_ids": ["a"]}]
    pre.save()
    def boom_synth(topic, items):
        raise RuntimeError("synth down")
    run_wiki(items_store=items_store, classified_state=str(tmp_path/"c.json"),
             topics_path=topics_path, out_dir=str(tmp_path/"topics"),
             classify=lambda it: it.categories, synthesize=boom_synth,
             resynth_threshold=1)
    d = TopicStore(topics_path).data["AI"]
    assert d["overview"] == "기존 좋은 개요"
    assert d["themes"][0]["name"] == "기존테마"


def test_run_wiki_synth_backoff_after_two_consecutive_failures(tmp_path):
    # (#14) 빈 합성 2회 연속 → threshold만큼 새 항목이 쌓일 때까지 스킵 (콜 낭비 방지)
    calls = {"n": 0}
    def empty_synth(topic, items):
        calls["n"] += 1
        return {"overview": "", "themes": [], "orphans": [], "related": []}
    items_store = str(tmp_path/"items.jsonl")
    append_items([mk("a", "글", categories=["AI"])], items_store)
    kw = dict(items_store=items_store, classified_state=str(tmp_path/"c.json"),
              topics_path=str(tmp_path/"t.json"), out_dir=str(tmp_path/"topics"),
              classify=lambda it: it.categories, synthesize=empty_synth,
              resynth_threshold=2)
    run_wiki(**kw)          # 실패 1
    run_wiki(**kw)          # 실패 2
    assert calls["n"] == 2
    run_wiki(**kw)          # 백오프 → 스킵
    assert calls["n"] == 2
    # 새 항목이 threshold(2)만큼 쌓이면 재시도
    append_items([mk("b", "글b", categories=["AI"]), mk("c", "글c", categories=["AI"])],
                 items_store)
    run_wiki(**kw)
    assert calls["n"] == 3


def test_run_wiki_synth_success_resets_fail_counter(tmp_path):
    # (#14) 성공하면 synth_fail 리셋 → 이후 미합성 재시도 경로 정상 동작
    from collector.topics import TopicStore
    responses = [{"overview": "", "themes": [], "orphans": [], "related": []},
                 {"overview": "좋은 개요", "themes": [], "orphans": [], "related": []}]
    def synth(topic, items):
        return responses.pop(0)
    items_store = str(tmp_path/"items.jsonl")
    append_items([mk("a", "글", categories=["AI"])], items_store)
    kw = dict(items_store=items_store, classified_state=str(tmp_path/"c.json"),
              topics_path=str(tmp_path/"t.json"), out_dir=str(tmp_path/"topics"),
              classify=lambda it: it.categories, synthesize=synth,
              resynth_threshold=2)
    run_wiki(**kw)          # 실패 1
    run_wiki(**kw)          # 성공 → 카운터 리셋
    d = TopicStore(str(tmp_path/"t.json")).data["AI"]
    assert d["overview"] == "좋은 개요"
    assert d.get("synth_fail", 0) == 0


def test_run_wiki_windowed_synth_maps_indexes_to_recent_items(tmp_path):
    # (#14) 26개 이상이면 최근 25개만 합성에 넘기고, 응답 번호도 그 윈도우 기준으로 매핑
    from collector.topics import TopicStore
    items_store = str(tmp_path/"items.jsonl")
    append_items([mk(f"id{i:02d}", f"글{i}", categories=["AI"]) for i in range(30)],
                 items_store)
    got = {}
    def synth(topic, items):
        got["items"] = list(items)
        return {"overview": "개요", "themes": [{"name": "테마", "intro": "", "indexes": [1]}],
                "orphans": [25], "related": []}
    run_wiki(items_store=items_store, classified_state=str(tmp_path/"c.json"),
             topics_path=str(tmp_path/"t.json"), out_dir=str(tmp_path/"topics"),
             classify=lambda it: it.categories, synthesize=synth, resynth_threshold=1)
    assert len(got["items"]) == 25                    # 최근 25개만 전달
    assert got["items"][0]["id"] == "id05"
    d = TopicStore(str(tmp_path/"t.json")).data["AI"]
    assert d["themes"][0]["item_ids"] == ["id05"]     # 번호 1 = 윈도우 첫 항목
    assert d["orphans"] == ["id29"]                   # 번호 25 = 최신 항목


def test_run_wiki_empty_classify_not_marked_seen(tmp_path):
    # (c) 분류가 빈 리스트 → seen 미마킹 (영구 유실 방지, 버그 픽스)
    import json
    items_store = str(tmp_path/"items.jsonl")
    append_items([mk("a", "글")], items_store)
    kw = dict(items_store=items_store, classified_state=str(tmp_path/"c.json"),
              topics_path=str(tmp_path/"t.json"), out_dir=str(tmp_path/"topics"),
              synthesize=_empty_synth, resynth_threshold=1)
    run_wiki(classify=lambda it: [], **kw)
    cl = json.load(open(str(tmp_path/"c.json"), encoding="utf-8"))
    assert "a" not in cl["seen"]                 # 유실 대신 재시도 대상으로 남는다
    # 다음 실행에서 분류가 성공하면 정상 편입 + seen 마킹
    run_wiki(classify=lambda it: ["AI"], **kw)
    cl = json.load(open(str(tmp_path/"c.json"), encoding="utf-8"))
    assert "a" in cl["seen"]
