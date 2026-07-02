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
    s.set_structure("AI 에이전트", "개요글", themes=[], orphans=[], related=["Claude"])
    assert s.needs_resynth("AI 에이전트", threshold=2) is False  # 카운터 리셋
    s.save()
    assert TopicStore(str(tmp_path / "topics.json")).data["AI 에이전트"]["overview"] == "개요글"

def test_corrupt_topics_json_backs_up_and_starts_empty(tmp_path):
    # corrupt JSON이어도 크래시 없이 .bak 백업 후 빈 상태로 시작
    path = tmp_path / "topics.json"
    path.write_text("[깨진 json", encoding="utf-8")
    s = TopicStore(str(path))
    assert s.topic_names() == []                        # 빈 상태
    assert (tmp_path / "topics.json.bak").exists()      # 원본 백업
    assert s.add_item("AI 에이전트", mk("a", "조코딩", "글a")) is True
    s.save()
    assert TopicStore(str(path)).topic_names() == ["AI 에이전트"]
