from collector.models import Item
from collector.digest import render_markdown, write_digest

def test_render_groups_by_source_and_includes_summary():
    items = [
        Item(source_name="조코딩", source_type="youtube", id="1",
             title="영상A", link="http://y/a", published="", summary="- 요약A"),
        Item(source_name="SaaStr", source_type="newsletter", id="2",
             title="글B", link="http://s/b", published="", summary="- 요약B"),
    ]
    md = render_markdown(items, date="2026-06-27")
    assert "# 2026-06-27 AI 요약" in md
    assert "조코딩" in md and "SaaStr" in md
    assert "요약A" in md and "[영상A](http://y/a)" in md

def test_write_digest_creates_dated_file(tmp_path):
    items = [Item(source_name="조코딩", source_type="youtube", id="1",
                  title="영상A", link="http://y/a", published="", summary="- 요약A")]
    path = write_digest(items, date="2026-06-27", out_dir=str(tmp_path))
    assert path.endswith("2026-06-27.md")
    with open(path, encoding="utf-8") as f:
        assert "요약A" in f.read()
