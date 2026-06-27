import os
from collector.models import Item
from collector.topics import TopicStore, write_pages

def test_write_pages_removes_stale_keeps_index(tmp_path):
    out = tmp_path / "topics"
    out.mkdir()
    (out / "옛주제.md").write_text("old", encoding="utf-8")   # 스테일 (삭제 대상)
    (out / "00-목차.md").write_text("idx", encoding="utf-8")  # 목차 (보존)

    s = TopicStore(str(tmp_path / "t.json"))
    s.add_item("AI 모델·기술", Item(source_name="조코딩", source_type="x", id="a",
               title="글a", link="http://a", published="2026-06-27", summary="요약"))
    write_pages(s, str(out))

    files = set(os.listdir(out))
    assert "AI 모델·기술.md" in files   # 현재 주제 생성됨
    assert "옛주제.md" not in files      # 스테일 삭제됨
    assert "00-목차.md" in files        # 목차 보존됨
