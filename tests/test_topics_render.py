from collector.models import Item
from collector.topics import TopicStore, render_page, write_pages

def test_render_and_write(tmp_path):
    s = TopicStore(str(tmp_path/"topics.json"))
    s.add_item("AI 에이전트", Item(source_name="조코딩", source_type="x", id="a",
               title="글a", link="http://a", published="2026-06-27", summary="요약a"))
    s.set_overview("AI 에이전트", "이 주제 개요입니다", ["Claude", "SaaS"])
    md = render_page("AI 에이전트", s.data["AI 에이전트"])
    assert "# AI 에이전트" in md
    assert "1개 출처" in md
    assert "이 주제 개요입니다" in md
    assert "[글a](http://a)" in md
    assert "[[Claude]]" in md and "[[SaaS]]" in md

    paths = write_pages(s, str(tmp_path/"topics"))
    assert any(p.endswith("AI 에이전트.md") for p in paths)
