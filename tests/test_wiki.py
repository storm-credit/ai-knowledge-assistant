from collector.models import Item
from collector.store import append_items
from collector.wiki import run_wiki

def mk(id, title, categories=None): return Item(source_name="조코딩", source_type="x", id=id,
                               title=title, link="http://"+id, published="2026-06-27", summary="요약",
                               categories=categories or [])

def test_run_wiki_classifies_and_writes(tmp_path):
    items_store = str(tmp_path/"items.jsonl")
    append_items([mk("a","에이전트 글"), mk("b","Claude 글")], items_store)

    def fake_classify(item, known):
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

    def fake_classify(item, known):
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
    def fake_classify(item, known):
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
             classify=lambda it,k: it.categories, synthesize=fake_struct, resynth_threshold=1)
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
             classify=lambda it,k: it.categories, synthesize=empty_synth,
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
              classify=lambda it,k: it.categories, synthesize=fake_struct,
              resynth_threshold=99)   # needs_resynth 비활성
    run_wiki(**kw)
    assert calls["n"] == 1            # 첫 실행에 1회 합성
    run_wiki(**kw)
    assert calls["n"] == 1            # 두 번째 실행에선 재합성 안 함 (플래그 가드)
