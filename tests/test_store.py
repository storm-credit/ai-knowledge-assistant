from collector.models import Item
from collector.store import append_items, load_items, archive_old_items

def test_append_and_load_roundtrip(tmp_path):
    p = str(tmp_path / "items.jsonl")
    items = [Item(source_name="조코딩", source_type="youtube", id="a",
                  title="제목A", link="http://a", published="2026-06-27",
                  summary="요약A", tags=["t1"])]
    append_items(items, p)
    append_items([Item(source_name="SaaStr", source_type="newsletter", id="b",
                       title="제목B", link="http://b", published="", summary="요약B")], p)
    out = load_items(p)
    assert len(out) == 2
    assert out[0].id == "a" and out[0].summary == "요약A"
    assert out[1].source_name == "SaaStr"

def test_load_missing_returns_empty(tmp_path):
    assert load_items(str(tmp_path / "none.jsonl")) == []

def test_load_old_style_line_defaults_categories(tmp_path):
    # 구버전 jsonl 줄은 categories 키가 없음 → 기본값 [] 적용 (하위호환)
    p = tmp_path / "items.jsonl"
    p.write_text(
        '{"source_name":"조코딩","source_type":"youtube","id":"a","title":"제목",'
        '"link":"http://a","published":"","raw_text":"","summary":"요약","tags":[]}\n',
        encoding="utf-8")
    out = load_items(str(p))
    assert len(out) == 1 and out[0].categories == []

def test_load_skips_corrupt_lines(tmp_path, capsys):
    # partial write로 깨진 줄이 있어도 정상 줄만 반환하고 경고만 출력 (cron 영구 사망 방지)
    p = tmp_path / "items.jsonl"
    good = ('{"source_name":"조코딩","source_type":"youtube","id":"%s","title":"제목",'
            '"link":"http://a","published":"","raw_text":"","summary":"요약","tags":[]}')
    p.write_text((good % "a") + "\n{깨진 줄...\n" + (good % "b") + "\n", encoding="utf-8")
    out = load_items(str(p))
    assert [it.id for it in out] == ["a", "b"]
    assert "skip" in capsys.readouterr().out   # 경고 출력

def test_append_skips_already_stored_ids(tmp_path):
    # 크래시 후 재실행 시 같은 항목이 다시 append 돼도 중복 저장되지 않는다
    p = str(tmp_path / "items.jsonl")
    a = Item(source_name="조코딩", source_type="youtube", id="a",
             title="제목A", link="http://a", published="", summary="요약A")
    b = Item(source_name="SaaStr", source_type="newsletter", id="b",
             title="제목B", link="http://b", published="", summary="요약B")
    append_items([a], p)
    append_items([a, b], p)   # a는 이미 저장됨 → skip
    out = load_items(p)
    assert [it.id for it in out] == ["a", "b"]

def test_load_ignores_unknown_keys(tmp_path):
    # 알 수 없는 키가 있어도 크래시 없이 로드 (Fix 5)
    p = tmp_path / "items.jsonl"
    p.write_text(
        '{"source_name":"조코딩","source_type":"youtube","id":"a","title":"제목",'
        '"link":"http://a","published":"","raw_text":"","summary":"요약","tags":[],'
        '"bogus":1}\n',
        encoding="utf-8")
    out = load_items(str(p))
    assert len(out) == 1 and out[0].id == "a"


def _mk(id, published="2026-06-27"):
    return Item(source_name="s", source_type="youtube", id=id, title="제목"+id,
                link="http://"+id, published=published, summary="요약"+id)

def test_load_limit_returns_last_n(tmp_path):
    # (#23) limit이 주어지면 파일 끝에서부터 마지막 N개만 로드 (최신 항목이 뒤에 append)
    p = str(tmp_path / "items.jsonl")
    append_items([_mk(f"id{i}") for i in range(5)], p)
    out = load_items(p, limit=2)
    assert [it.id for it in out] == ["id3", "id4"]

def test_load_limit_none_loads_all(tmp_path):
    # (#23) 기본 None은 기존과 동일하게 전량 로드
    p = str(tmp_path / "items.jsonl")
    append_items([_mk(f"id{i}") for i in range(3)], p)
    assert len(load_items(p)) == 3
    assert len(load_items(p, limit=None)) == 3

def test_archive_moves_old_keeps_recent(tmp_path):
    # (#23) keep_days보다 오래된 항목은 아카이브로, 최근 항목은 원본에 유지
    from datetime import date
    p = str(tmp_path / "items.jsonl")
    append_items([_mk("old", "2026-01-01"), _mk("recent", "2026-06-30")], p)
    archive_old_items(p, keep_days=90, today=date(2026, 7, 8))
    assert [it.id for it in load_items(p)] == ["recent"]
    arc = load_items(str(tmp_path / "items-archive.jsonl"))
    assert [it.id for it in arc] == ["old"]

def test_archive_keeps_items_without_published(tmp_path):
    # (#23) published 없는 항목은 판단 불가 → 스킵(원본 유지)
    from datetime import date
    p = str(tmp_path / "items.jsonl")
    append_items([_mk("nopub", ""), _mk("old", "2026-01-01")], p)
    archive_old_items(p, keep_days=90, today=date(2026, 7, 8))
    assert sorted(it.id for it in load_items(p)) == ["nopub"]

def test_archive_preserves_corrupt_lines_in_original(tmp_path):
    # (#23) 원본의 깨진 줄은 손실 없이 원본에 보존
    from datetime import date
    p = tmp_path / "items.jsonl"
    good = ('{"source_name":"s","source_type":"youtube","id":"%s","title":"t",'
            '"link":"http://x","published":"%s","summary":"y"}')
    p.write_text((good % ("old", "2026-01-01")) + "\n{깨진...\n"
                 + (good % ("recent", "2026-06-30")) + "\n", encoding="utf-8")
    archive_old_items(str(p), keep_days=90, today=date(2026, 7, 8))
    raw = p.read_text(encoding="utf-8")
    assert "깨진" in raw                       # 깨진 줄 보존
    assert [it.id for it in load_items(str(p))] == ["recent"]

def test_archive_missing_original_is_noop(tmp_path):
    # (#23) 원본이 없으면 no-op (아카이브 파일도 생기지 않음)
    import os
    p = str(tmp_path / "items.jsonl")
    archive_old_items(p)
    assert not os.path.exists(str(tmp_path / "items-archive.jsonl"))
