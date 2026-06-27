import os
from collector.models import Item
from collector.topics import TopicStore, render_index, write_index

def mk(id, src, title):
    return Item(source_name=src, source_type="x", id=id, title=title,
                link="http://"+id, published="2026-06-27", summary="요약")

def test_render_and_write_index(tmp_path):
    s = TopicStore(str(tmp_path/"topics.json"))
    # "AI 모델·기술": 2 items, 2 sources
    s.add_item("AI 모델·기술", mk("a", "조코딩", "글a"))
    s.add_item("AI 모델·기술", mk("b", "SaaStr", "글b"))
    # "기타": 1 item, 1 source
    s.add_item("기타", mk("c", "조코딩", "글c"))

    md = render_index(s)
    assert "# 📚 목차" in md
    assert "[[AI 모델·기술]]" in md and "[[기타]]" in md
    assert "2건 · 2개 출처" in md
    assert "1건 · 1개 출처" in md
    # item count desc: 모델·기술(2) 먼저, 기타(1) 나중
    assert md.index("AI 모델·기술") < md.index("기타")

    p = write_index(s, str(tmp_path/"topics"))
    assert p.endswith("00-목차.md")
    assert os.path.exists(p)
