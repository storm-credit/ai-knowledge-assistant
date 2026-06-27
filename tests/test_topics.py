from collector.models import Item
from collector.topics import TopicStore

def mk(id, src, title):
    return Item(source_name=src, source_type="x", id=id, title=title,
                link="http://"+id, published="2026-06-27", summary="요약-"+id)

def test_add_dedup_sources_and_resynth(tmp_path):
    s = TopicStore(str(tmp_path / "topics.json"))
    assert s.add_item("AI 에이전트", mk("a","조코딩","글a")) is True
    assert s.add_item("AI 에이전트", mk("a","조코딩","글a")) is False  # 중복 id
    assert s.add_item("AI 에이전트", mk("b","SaaStr","글b")) is True
    d = s.data["AI 에이전트"]
    assert len(d["items"]) == 2
    assert sorted(d["sources"]) == ["SaaStr", "조코딩"]   # 출처 2개
    assert s.needs_resynth("AI 에이전트", threshold=2) is True
    s.set_overview("AI 에이전트", "개요글", ["Claude"])
    assert s.needs_resynth("AI 에이전트", threshold=2) is False  # 카운터 리셋
    s.save()
    assert TopicStore(str(tmp_path / "topics.json")).data["AI 에이전트"]["overview"] == "개요글"
