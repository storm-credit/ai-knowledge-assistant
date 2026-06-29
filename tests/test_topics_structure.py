from collector.models import Item
from collector.topics import TopicStore

def _mk(i): return Item(source_name="s", source_type="x", id=f"id{i}",
                        title=f"T{i}", link=f"http://{i}", published="2026-06-29", summary=f"s{i}")

def test_set_structure_maps_indexes_to_ids(tmp_path):
    s = TopicStore(str(tmp_path/"t.json"))
    for i in (1,2,3,4): s.add_item("AI", _mk(i))
    s.set_structure("AI", "개요글",
                    themes=[{"name":"테마1","intro":"정리1","indexes":[1,3]}],
                    orphans=[4], related=["Claude"])
    d = s.data["AI"]
    assert d["overview"] == "개요글"
    assert d["themes"][0]["name"] == "테마1"
    assert d["themes"][0]["item_ids"] == ["id1","id3"]   # 번호→id 매핑
    assert d["orphans"] == ["id4"]
    assert d["new_since_synth"] == 0                      # 카운터 리셋
    assert d["synthesized"] is True                       # 합성 완료 플래그
