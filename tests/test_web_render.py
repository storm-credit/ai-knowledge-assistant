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


def test_learning_card_stays_one_article_with_code_block():
    # 학습 카드는 헤딩 대신 굵은 라벨 + 코드펜스 → 기사 카드 하나로 유지돼야
    md = (
        "## 개발\n테마 설명\n\n"
        "### [파이썬 기초](http://a)\n노마드코더 · 2026-07-01\n\n"
        "**핵심 개념**\n- 변수와 타입\n\n"
        "```python\nx = 1\nprint(x)\n```\n\n"
        "**한 줄 정리**\n기초를 다진다\n"
    )
    html = render.render_markdown(md)
    # 카드 분리 안 깨짐 (핵심 개념 라벨 → 학습 뱃지 클래스가 붙음)
    assert html.count('<div class="article article--learning">') == 1
    assert "<pre>" in html and "<code" in html          # 코드블록 렌더
    assert "<strong>핵심 개념</strong>" in html          # 굵은 라벨
    assert "x = 1" in html


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


# --- 카드 E: 코드펜스 안전 위키링크 ---

def test_wikilinks_skip_code_fences():
    md = (
        "본문 [[AI 모델·기술]] 링크\n\n"
        "```bash\nif [[ -z \"$x\" ]]; then echo ok; fi\n```\n"
    )
    html = render.render_markdown(md)
    assert 'href="/topic/AI%20%EB%AA%A8%EB%8D%B8' in html  # 본문은 링크로
    assert "[[ -z" in html                                  # 코드펜스는 보존
    assert '/topic/%20-z' not in html and "/topic/ -z" not in html


def test_wikilinks_skip_inline_code():
    html = render.render_markdown("설명 `[[ -n \"$y\" ]]` 와 [[기타]]")
    assert "[[ -n" in html
    assert 'href="/topic/%EA%B8%B0%ED%83%80"' in html


# --- 카드 E: 학습 카드 뱃지 ---

def test_learning_article_gets_learning_class():
    md = (
        "### [파이썬 기초](http://a)\n노마드코더 · 2026-07-01\n\n"
        "**핵심 개념**\n- 변수와 타입\n\n"
        "### [일반 기사](http://b)\n출처 · 2026-07-01\n\n일반 요약\n"
    )
    html = render.render_markdown(md)
    assert html.count('<div class="article article--learning">') == 1
    assert html.count('<div class="article">') == 1  # 일반 기사엔 뱃지 클래스 없음


def test_learning_badge_css_present():
    from web.app import BASE_CSS
    assert ".article--learning" in BASE_CSS
    assert "overflow-wrap:anywhere" in BASE_CSS


# --- 카드 E: 맨몸 URL 자동 링크 ---

def test_bare_url_becomes_link():
    html = render.render_markdown("참고: https://example.com/post 확인\n")
    assert '<a href="https://example.com/post">' in html


def test_markdown_link_not_double_converted():
    html = render.render_markdown("[제목](https://example.com/a) 요약\n")
    assert html.count("https://example.com/a") == 1
    assert '<a href="https://example.com/a">제목</a>' in html


def test_url_in_code_not_linked():
    html = render.render_markdown("```\ncurl https://example.com/api\n```\n")
    assert "<a " not in html


# --- 카드 E: '오늘' 바로가기 + 이전/다음 ---

def _fake_entries():
    return [
        render.DailyEntry(date="2026-07-02", title="요약3"),
        render.DailyEntry(date="2026-07-01", title="요약2"),
        render.DailyEntry(date="2026-06-30", title="요약1"),
    ]


def test_nav_today_links_latest_daily(monkeypatch):
    from web import app as webapp
    monkeypatch.setattr(webapp.render, "list_dailies", _fake_entries)
    body = webapp.app.test_client().get("/").get_data(as_text=True)
    assert 'href="/daily/2026-07-02">오늘</a>' in body


def test_nav_today_falls_back_without_dailies(monkeypatch):
    from web import app as webapp
    monkeypatch.setattr(webapp.render, "list_dailies", lambda: [])
    body = webapp.app.test_client().get("/").get_data(as_text=True)
    assert 'href="/daily">오늘</a>' in body


def test_daily_prev_next_nav(monkeypatch):
    from web import app as webapp
    monkeypatch.setattr(webapp.render, "list_dailies", _fake_entries)
    monkeypatch.setattr(webapp.render, "load_daily", lambda d: (d, "<p>본문</p>"))
    client = webapp.app.test_client()
    # 가운데 날짜: 양쪽 다 있음 (topbar '오늘'과 구분되게 화살표 텍스트로 확인)
    body = client.get("/daily/2026-07-01").get_data(as_text=True)
    assert "← 2026-06-30" in body   # 이전날
    assert "2026-07-02 →" in body   # 다음날
    # 최신 날짜: 다음날 없음
    body = client.get("/daily/2026-07-02").get_data(as_text=True)
    assert "← 2026-07-01" in body
    assert "→" not in body
    # 가장 오래된 날짜: 이전날 없음
    body = client.get("/daily/2026-06-30").get_data(as_text=True)
    assert "2026-07-01 →" in body
    assert "←" not in body
