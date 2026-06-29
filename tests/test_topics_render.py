from collector.models import Item
from collector.topics import TopicStore, render_page, write_pages

def test_render_and_write(tmp_path):
    s = TopicStore(str(tmp_path/"topics.json"))
    s.add_item("AI 에이전트", Item(source_name="조코딩", source_type="x", id="a",
               title="글a", link="http://a", published="2026-06-27",
               summary="- 핵심 포인트 A\n- 핵심 포인트 B"))
    s.set_overview("AI 에이전트", "이 주제 개요입니다", ["Claude"])
    md = render_page("AI 에이전트", s.data["AI 에이전트"])
    assert "> [!abstract] 개요" in md and "이 주제 개요입니다" in md  # 개요 콜아웃
    assert "## 관련 소식" in md                     # 테마 없으면 평면 폴백
    assert "### [글a](http://a)" in md            # 항목 제목(링크)
    assert "조코딩" in md                          # 출처/날짜
    assert "핵심 포인트 A" in md and "핵심 포인트 B" in md   # 요약 내용 표시
    assert "[[Claude]]" in md
    paths = write_pages(s, str(tmp_path/"topics"))
    assert any(p.endswith("AI 에이전트.md") for p in paths)


def test_render_themed_page(tmp_path):
    from collector.models import Item
    from collector.topics import TopicStore, render_page
    s = TopicStore(str(tmp_path/"t.json"))
    for i in (1,2): s.add_item("AI", Item(source_name="노정석", source_type="x",
        id=f"id{i}", title=f"글{i}", link=f"http://{i}", published="2026-06-29",
        summary=f"요약{i}"))
    s.set_structure("AI", "전체 개요다",
                    themes=[{"name":"모델 경쟁","intro":"경쟁 치열","indexes":[1]}],
                    orphans=[2], related=["Claude"])
    md = render_page("AI", s.data["AI"])
    assert "> [!abstract] 개요" in md and "전체 개요다" in md
    assert "## 모델 경쟁" in md and "경쟁 치열" in md
    assert "[글1](http://1)" in md and "요약1" in md       # 테마 안 항목+내용
    assert "## 짚어둘 단신" in md and "[글2](http://2)" in md  # 단신
    assert "[[Claude]]" in md
