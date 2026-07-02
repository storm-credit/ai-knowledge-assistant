from collector.state import StateStore

def test_new_item_then_marked_then_not_new(tmp_path):
    path = tmp_path / "seen.json"
    s = StateStore(str(path))
    assert s.is_new("yt:abc") is True
    s.mark_seen("yt:abc")
    s.save()

    s2 = StateStore(str(path))   # 새로 로드해도 기억
    assert s2.is_new("yt:abc") is False

def test_corrupt_seen_json_backs_up_and_starts_empty(tmp_path):
    # corrupt JSON이어도 크래시 없이 .bak 백업 후 빈 상태로 시작
    path = tmp_path / "seen.json"
    path.write_text("{깨진 json", encoding="utf-8")
    s = StateStore(str(path))
    assert s.is_new("x") is True                       # 빈 상태
    assert (tmp_path / "seen.json.bak").exists()       # 원본 백업
    s.mark_seen("x")
    s.save()
    assert StateStore(str(path)).is_new("x") is False  # 이후 정상 동작
