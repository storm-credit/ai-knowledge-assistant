from collector.state import StateStore

def test_new_item_then_marked_then_not_new(tmp_path):
    path = tmp_path / "seen.json"
    s = StateStore(str(path))
    assert s.is_new("yt:abc") is True
    s.mark_seen("yt:abc")
    s.save()

    s2 = StateStore(str(path))   # 새로 로드해도 기억
    assert s2.is_new("yt:abc") is False
