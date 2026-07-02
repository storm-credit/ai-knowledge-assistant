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

def test_write_digest_merges_same_day_rerun(tmp_path):
    # 당일 재실행(쿼터 초과 후 재시도) 시 아침 수집분이 유실되면 안 된다
    morning = [
        Item(source_name="조코딩", source_type="youtube", id="1",
             title="아침A", link="http://y/a", published="", summary="- 요약A"),
        Item(source_name="SaaStr", source_type="newsletter", id="2",
             title="아침B", link="http://s/b", published="", summary="- 요약B"),
    ]
    write_digest(morning, date="2026-07-02", out_dir=str(tmp_path))

    retry = [
        Item(source_name="SaaStr", source_type="newsletter", id="2",
             title="아침B", link="http://s/b", published="", summary="- 요약B"),   # 중복
        Item(source_name="SaaStr", source_type="newsletter", id="3",
             title="재시도C", link="http://s/c", published="", summary="- 요약C"),
        Item(source_name="NewSrc", source_type="newsletter", id="4",
             title="신규D", link="http://n/d", published="", summary="- 요약D"),
    ]
    path = write_digest(retry, date="2026-07-02", out_dir=str(tmp_path))

    with open(path, encoding="utf-8") as f:
        content = f.read()
    # 아침분·재시도분 모두 존재
    for t in ("아침A", "아침B", "재시도C", "신규D"):
        assert t in content
    # 중복 항목은 한 번만
    assert content.count("http://s/b") == 1
    # 기존 출처 섹션 재사용(중복 섹션 없음) + 새 출처는 새 섹션
    assert content.count("## SaaStr") == 1
    assert "## NewSrc" in content
    # 총 건수 헤더 갱신
    assert "총 4건" in content

def test_write_digest_merge_keeps_existing_summaries(tmp_path):
    # 병합 시 기존 항목의 요약 본문이 보존된다
    write_digest([Item(source_name="조코딩", source_type="youtube", id="1",
                       title="아침A", link="http://y/a", published="",
                       summary="- 소중한 아침 요약")],
                 date="2026-07-02", out_dir=str(tmp_path))
    path = write_digest([Item(source_name="조코딩", source_type="youtube", id="9",
                              title="오후Z", link="http://y/z", published="",
                              summary="- 오후 요약")],
                        date="2026-07-02", out_dir=str(tmp_path))
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "소중한 아침 요약" in content and "오후 요약" in content
    assert "총 2건" in content
