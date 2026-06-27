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
