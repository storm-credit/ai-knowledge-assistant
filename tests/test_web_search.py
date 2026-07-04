"""#19 노트 전체 검색 — search_notes 순수 함수 + /search 라우트."""
from pathlib import Path

from web import render


def _write(dir_: Path, name: str, text: str, encoding: str = "utf-8") -> None:
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / name).write_text(text, encoding=encoding)


def _dirs(tmp_path: Path):
    t, d, l = tmp_path / "topics", tmp_path / "daily", tmp_path / "learn"
    for p in (t, d, l):
        p.mkdir()
    return t, d, l


# --- search_notes: 매칭 ---

def test_search_matches_across_three_dirs(tmp_path):
    t, d, l = _dirs(tmp_path)
    _write(t, "AI 모델·기술.md", "# AI 모델·기술\n\n하네스 엔지니어링이 핵심.\n")
    _write(d, "2026-07-01.md", "# 2026-07-01 AI 요약\n\n하네스 관련 기사.\n")
    _write(l, "하네스.md", "# 하네스\n\n하네스란 실행 틀.\n")
    hits = render.search_notes("하네스", topics_dir=t, daily_dir=d, learn_dir=l)
    assert {h.kind for h in hits} == {"topic", "daily", "learn"}
    topic_hit = next(h for h in hits if h.kind == "topic")
    assert topic_hit.name == "AI 모델·기술"
    assert topic_hit.title == "AI 모델·기술"
    assert "하네스" in topic_hit.snippet


def test_search_is_case_insensitive(tmp_path):
    t, d, l = _dirs(tmp_path)
    _write(t, "도구.md", "# 도구\n\nMCP 서버 활용법.\n")
    hits = render.search_notes("mcp", topics_dir=t, daily_dir=d, learn_dir=l)
    assert len(hits) == 1
    assert "MCP" in hits[0].snippet  # 매칭어는 원문 그대로


def test_search_empty_or_blank_query_returns_nothing(tmp_path):
    t, d, l = _dirs(tmp_path)
    _write(t, "도구.md", "# 도구\n\n본문\n")
    assert render.search_notes("", topics_dir=t, daily_dir=d, learn_dir=l) == []
    assert render.search_notes("   ", topics_dir=t, daily_dir=d, learn_dir=l) == []


def test_search_caps_three_hits_per_file_and_fifty_total(tmp_path):
    t, d, l = _dirs(tmp_path)
    _write(t, "많음.md", "# 많음\n" + "매칭 줄\n" * 10)
    hits = render.search_notes("매칭", topics_dir=t, daily_dir=d, learn_dir=l)
    assert len(hits) == 3  # 파일당 최대 3
    for i in range(20):
        _write(d, f"2026-06-{i + 1:02d}.md", "# 요약\n" + "매칭 줄\n" * 5)
    hits = render.search_notes("매칭", topics_dir=t, daily_dir=d, learn_dir=l)
    assert len(hits) == 50  # 전체 최대 50


def test_search_snippet_trimmed_around_match(tmp_path):
    t, d, l = _dirs(tmp_path)
    long_line = "가" * 200 + " 하네스 " + "나" * 200
    _write(t, "긴줄.md", f"# 긴줄\n\n{long_line}\n")
    hits = render.search_notes("하네스", topics_dir=t, daily_dir=d, learn_dir=l)
    assert len(hits) == 1
    assert "하네스" in hits[0].snippet
    assert len(hits[0].snippet) <= 170  # ~160자 + 말줄임


def test_search_reads_utf8_bom(tmp_path):
    t, d, l = _dirs(tmp_path)
    _write(l, "밤.md", "# 밤\n\nBOM 파일 매칭.\n", encoding="utf-8-sig")
    hits = render.search_notes("BOM", topics_dir=t, daily_dir=d, learn_dir=l)
    assert len(hits) == 1
    assert hits[0].title == "밤"  # BOM이 제목에 안 섞임


def test_search_skips_toc_and_non_date_daily(tmp_path):
    t, d, l = _dirs(tmp_path)
    _write(t, "00-목차.md", "# 목차\n- [[도구]] — 매칭 1건\n")
    _write(d, "stray.md", "# stray\n매칭 줄\n")  # 날짜 형식 아님 → 상세 라우트 없음
    hits = render.search_notes("매칭", topics_dir=t, daily_dir=d, learn_dir=l)
    assert hits == []


# --- /search 라우트 ---

def _client(tmp_path, monkeypatch):
    from web import app as webapp
    t, d, l = _dirs(tmp_path)
    _write(t, "AI 도구.md", "# AI 도구\n\n하네스 활용 정리.\n")
    _write(d, "2026-07-01.md", "# 2026-07-01 AI 요약\n\n하네스 기사.\n")
    monkeypatch.setattr(webapp.render, "TOPICS_DIR", t)
    monkeypatch.setattr(webapp.render, "DAILY_DIR", d)
    monkeypatch.setattr(webapp.render, "LEARN_DIR", l)
    return webapp.app.test_client()


def test_search_route_renders_hits_with_links(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    res = client.get("/search?q=하네스")
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert 'href="/topic/AI%20%EB%8F%84%EA%B5%AC"' in body  # 상세 링크
    assert 'href="/daily/2026-07-01"' in body
    assert "📚" in body and "🗓️" in body  # kind 아이콘


def test_search_route_no_query_and_no_result(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    assert client.get("/search").status_code == 200
    body = client.get("/search?q=zzz없는말zzz").get_data(as_text=True)
    assert "0건" in body


def test_search_route_escapes_script_in_query(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    body = client.get("/search?q=<script>alert(1)</script>").get_data(as_text=True)
    assert "<script>alert(1)" not in body
    assert "&lt;script&gt;" in body


def test_search_route_escapes_script_in_snippet(tmp_path, monkeypatch):
    from web import app as webapp
    t, d, l = _dirs(tmp_path)
    _write(t, "오염.md", "# 오염\n\n매칭 <script>alert(1)</script> 줄.\n")
    monkeypatch.setattr(webapp.render, "TOPICS_DIR", t)
    monkeypatch.setattr(webapp.render, "DAILY_DIR", d)
    monkeypatch.setattr(webapp.render, "LEARN_DIR", l)
    body = webapp.app.test_client().get("/search?q=매칭").get_data(as_text=True)
    assert "<script>alert(1)" not in body


def test_topbar_has_search_form(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    body = client.get("/").get_data(as_text=True)
    assert 'action="/search"' in body
    assert 'name="q"' in body
