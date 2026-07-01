from pathlib import Path

from web import render


def _write(dir_: Path, name: str, text: str) -> None:
    (dir_ / name).write_text(text, encoding="utf-8")


def test_wikilinks_become_topic_links():
    html = render.render_markdown("관련: [[AI 모델·기술]] 참고")
    assert 'href="/topic/AI%20%EB%AA%A8%EB%8D%B8' in html
    assert ">AI 모델·기술<" in html


def test_callout_is_rendered_as_styled_div():
    md = "> [!abstract] 개요\n> 첫 줄\n> 둘째 줄\n"
    html = render.render_markdown(md)
    assert 'class="callout callout-abstract"' in html
    assert "개요" in html
    assert "첫 줄<br>둘째 줄" in html


def test_callout_body_is_escaped():
    html = render.render_markdown("> [!note] t\n> <script>bad</script>\n")
    assert "<script>bad" not in html
    assert "&lt;script&gt;" in html


def test_list_topics_reads_toc_order(tmp_path):
    _write(tmp_path, "00-목차.md",
           "# 📚 목차\n- [[AI 활용·도구]] — 42건 · 7개 출처\n- [[기타]] — 9건 · 6개 출처\n")
    _write(tmp_path, "AI 활용·도구.md", "# AI 활용·도구\n본문\n")
    _write(tmp_path, "기타.md", "# 기타\n본문\n")
    cards = render.list_topics(tmp_path)
    assert [c.name for c in cards] == ["AI 활용·도구", "기타"]
    assert cards[0].count == "42건 · 7개 출처"


def test_list_topics_falls_back_to_scan(tmp_path):
    _write(tmp_path, "Alpha.md", "# Alpha\n")
    _write(tmp_path, "Beta.md", "# Beta\n")
    names = [c.name for c in render.list_topics(tmp_path)]
    assert names == ["Alpha", "Beta"]


def test_articles_are_wrapped_in_cards():
    md = (
        "## 테마\n테마 설명\n\n"
        "### [기사1](http://a)\n출처 · 2026-06-27\n\n요약1\n\n"
        "### [기사2](http://b)\n출처 · 2026-06-28\n\n요약2\n"
    )
    html = render.render_markdown(md)
    # one card per h3 article, theme heading left uncarded
    assert html.count('<div class="article">') == 2
    assert html.count("</div>") == 2
    # theme heading is not inside a card
    assert '<div class="article"><h2' not in html
    assert '<div class="article"><h3' in html


def test_wrap_articles_noop_without_h3():
    html = render.render_markdown("## 짚어둘 단신\n- [a](http://a) · src · 2026-06-27\n")
    assert '<div class="article">' not in html


def test_load_topic_strips_title_and_renders(tmp_path):
    _write(tmp_path, "AI 모델·기술.md", "# AI 모델·기술\n\n## 테마\n내용\n")
    title, html = render.load_topic("AI 모델·기술", tmp_path)
    assert title == "AI 모델·기술"
    assert "<h1" not in html  # title peeled off, rendered by template instead
    assert "<h2>테마</h2>" in html


def test_load_topic_missing_returns_none(tmp_path):
    assert render.load_topic("nope", tmp_path) is None


def test_load_topic_rejects_path_traversal(tmp_path):
    assert render.load_topic("../secret", tmp_path) is None
    assert render.load_topic("a/b", tmp_path) is None


def test_list_dailies_newest_first(tmp_path):
    _write(tmp_path, "2026-06-30.md", "# 2026-06-30 AI 요약\n")
    _write(tmp_path, "2026-07-01.md", "# 2026-07-01 AI 요약\n")
    _write(tmp_path, "notes.md", "# stray\n")  # ignored: not a date
    entries = render.list_dailies(tmp_path)
    assert [e.date for e in entries] == ["2026-07-01", "2026-06-30"]


def test_load_daily_validates_date_format(tmp_path):
    _write(tmp_path, "2026-07-01.md", "# 2026-07-01 AI 요약\n본문\n")
    assert render.load_daily("2026-07-01", tmp_path) is not None
    assert render.load_daily("bad", tmp_path) is None
