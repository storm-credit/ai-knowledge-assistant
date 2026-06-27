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
    def fake_synth(topic, items): return (f"{topic} 개요", ["기타"])

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
    def fake_synth(topic, items): return (f"{topic} 개요", ["기타"])

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
    def fake_synth(topic, items): return (f"{topic} 개요", [])

    paths = run_wiki(items_store=items_store,
                     classified_state=str(tmp_path/"classified.json"),
                     topics_path=str(tmp_path/"topics.json"),
                     out_dir=str(tmp_path/"topics"),
                     classify=fake_classify, synthesize=fake_synth, resynth_threshold=1)
    assert calls["n"] == 0                       # classify 미호출 → LLM 0콜
    names = [p.split("\\")[-1].split("/")[-1] for p in paths]
    assert "Claude.md" in names                  # 항목이 Claude 주제로 들어감
