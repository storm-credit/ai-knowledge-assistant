from collector.mdutil import safe_md_link


def test_https_link_renders_unchanged():
    assert safe_md_link("글", "https://a.b/c") == "[글](https://a.b/c)"
    assert safe_md_link("글", "http://a.b/c") == "[글](http://a.b/c)"


def test_javascript_scheme_drops_link():
    # javascript: 등 비 http(s) 스킴은 링크 없이 제목만
    assert safe_md_link("제목", "javascript:alert(1)") == "제목"
    assert safe_md_link("제목", " JaVaScRiPt:alert(1)") == "제목"
    assert safe_md_link("제목", "data:text/html,x") == "제목"
    assert safe_md_link("제목", "") == "제목"
    assert safe_md_link("제목", None) == "제목"


def test_brackets_in_title_are_escaped():
    # 제목의 ']('로 링크 구조를 주입하지 못한다
    out = safe_md_link("공지](javascript:alert(1)) [속보", "https://a.b/c")
    assert out == "[공지\\](javascript:alert(1)) \\[속보](https://a.b/c)"


def test_parens_in_link_are_encoded():
    out = safe_md_link("글", "https://a.b/c(1)")
    assert out == "[글](https://a.b/c%281%29)"


def test_digest_neutralizes_javascript_link():
    from collector.digest import render_markdown
    from collector.models import Item
    items = [Item(source_name="src", source_type="rss", id="1",
                  title="악성글", link="javascript:alert(1)", published="",
                  summary="- 요약")]
    md = render_markdown(items, date="2026-07-02")
    assert "javascript:" not in md
    assert "악성글" in md


def test_topics_neutralize_javascript_links():
    from collector.topics import render_page
    t = {"items": [
            {"id": "a", "title": "본문악성", "link": "javascript:alert(1)",
             "source": "s", "date": "2026-07-02", "summary": "요약"},
            {"id": "b", "title": "단신악성", "link": "javascript:alert(2)",
             "source": "s", "date": "2026-07-02", "summary": ""},
         ],
         "sources": ["s"], "overview": "개요", "related": [],
         "themes": [{"name": "테마", "intro": "", "item_ids": ["a"]}],
         "orphans": ["b"]}
    md = render_page("주제", t)
    assert "javascript:" not in md
    assert "본문악성" in md and "단신악성" in md
