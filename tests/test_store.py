from collector.models import Item
from collector.store import append_items, load_items

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
