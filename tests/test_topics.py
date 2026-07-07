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

def test_set_structure_maps_indexes_against_window(tmp_path):
    # (#14) window가 주입되면 응답 번호를 전체 items가 아닌 윈도우 기준으로 매핑
    s = TopicStore(str(tmp_path / "topics.json"))
    for i in range(4):
        s.add_item("AI", mk(f"id{i}", "s", f"글{i}"))
    window = s.data["AI"]["items"][-2:]              # id2, id3
    s.set_structure("AI", "개요", themes=[{"name": "테마", "intro": "", "indexes": [1]}],
                    orphans=[2], related=[], window=window)
    d = s.data["AI"]
    assert d["themes"][0]["item_ids"] == ["id2"]     # 번호 1 = 윈도우 첫 항목
    assert d["orphans"] == ["id3"]


def test_synth_fail_counter_and_backoff(tmp_path):
    # (#14) 2회 연속 실패 → 백오프 + new_since_synth 리셋, 성공 시 카운터 리셋
    s = TopicStore(str(tmp_path / "topics.json"))
    s.add_item("AI", mk("a", "s", "글a"))
    assert s.synth_backoff("AI") is False
    s.record_synth_failure("AI")
    assert s.synth_backoff("AI") is False            # 1회 실패로는 백오프 안 함
    s.record_synth_failure("AI")
    assert s.synth_backoff("AI") is True
    assert s.data["AI"]["new_since_synth"] == 0      # threshold 재충전까지 스킵
    s.set_structure("AI", "개요", themes=[], orphans=[], related=[])
    assert s.data["AI"]["synth_fail"] == 0           # 성공 시 리셋
    assert s.synth_backoff("AI") is False


def test_page_filename_replaces_forbidden_chars(tmp_path):
    # (#16) 파일명 금지문자 치환 규칙을 공개 함수로 노출 (웹측과 규칙 공유)
    import os
    from collector.topics import page_filename, write_pages
    assert page_filename('C/C++: "질문?"') == 'C_C++_ _질문__.md'
    assert page_filename("a\\b|c<d>e*f") == "a_b_c_d_e_f.md"
    assert page_filename("  ") == "untitled.md"      # 빈 이름은 untitled
    # write_pages가 같은 규칙을 사용
    s = TopicStore(str(tmp_path / "topics.json"))
    s.add_item("A/B:C", mk("a", "s", "글a"))
    paths = write_pages(s, str(tmp_path / "out"))
    assert os.path.basename(paths[0]) == page_filename("A/B:C") == "A_B_C.md"


def test_prune_topic_trims_oldest_and_cleans_refs(tmp_path):
    # (#23) max_items 초과 시 오래된 것부터 절삭, themes/orphans의 사라진 id 참조도 정리
    s = TopicStore(str(tmp_path / "topics.json"))
    for i in range(5):
        s.add_item("AI", mk(f"id{i}", "s", f"글{i}"))
    # id0(오래됨)을 테마에, id0+id4를 orphan에 참조시킨다
    s.data["AI"]["themes"] = [{"name": "T", "intro": "", "item_ids": ["id0", "id3"]}]
    s.data["AI"]["orphans"] = ["id0", "id4"]
    s.prune_topic("AI", max_items=3)
    d = s.data["AI"]
    assert [it["id"] for it in d["items"]] == ["id2", "id3", "id4"]   # 오래된 id0,id1 절삭
    assert d["themes"][0]["item_ids"] == ["id3"]                       # 사라진 id0 참조 제거
    assert d["orphans"] == ["id4"]                                     # 사라진 id0 참조 제거

def test_prune_topic_noop_when_under_limit(tmp_path):
    # (#23) 상한 이하면 아무것도 바꾸지 않는다
    s = TopicStore(str(tmp_path / "topics.json"))
    for i in range(3):
        s.add_item("AI", mk(f"id{i}", "s", f"글{i}"))
    s.prune_topic("AI", max_items=10)
    assert [it["id"] for it in s.data["AI"]["items"]] == ["id0", "id1", "id2"]

def test_prune_topic_unknown_topic_is_safe(tmp_path):
    # (#23) 없는 주제 prune은 크래시 없이 no-op
    s = TopicStore(str(tmp_path / "topics.json"))
    s.prune_topic("없음", max_items=5)


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
