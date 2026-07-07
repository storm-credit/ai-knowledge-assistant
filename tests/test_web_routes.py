"""#22 웹 라우트 보강 테스트 — traversal·404 경계 (기존 테스트와 중복 없는 케이스만)."""
from pathlib import Path

import pytest

from web import app as webapp


@pytest.fixture()
def client():
    return webapp.app.test_client()


def test_topic_url_encoded_traversal_404(client):
    # ..%2F가 디코딩돼 상위 디렉터리로 나가면 안 된다
    assert client.get("/topic/..%2Fsecret").status_code == 404
    assert client.get("/topic/..%5Csecret").status_code == 404  # 백슬래시(윈도)


def test_topic_missing_404(client):
    assert client.get("/topic/이런주제없음").status_code == 404


def test_daily_bad_date_format_404(client):
    assert client.get("/daily/2026-7-1").status_code == 404     # 자릿수 틀림
    assert client.get("/daily/notadate").status_code == 404
    assert client.get("/daily/2026-07-01.md").status_code == 404  # 확장자 주입


def test_learn_url_encoded_traversal_404(tmp_path, client, monkeypatch):
    # 파일이 실제로 존재해도 인코딩된 traversal로는 못 읽어야 한다
    (tmp_path / "learn").mkdir()
    (tmp_path / "secret.md").write_text("# 비밀\n", encoding="utf-8")
    monkeypatch.setattr(webapp.render, "LEARN_DIR", tmp_path / "learn")
    assert client.get("/learn/..%2Fsecret").status_code == 404


# --- #21 홈 '오늘 중심' 개편 ---

def _dailies():
    from web import render
    return [render.DailyEntry(date="2026-07-08", title="오늘의 AI 요약"),
            render.DailyEntry(date="2026-07-07", title="어제 요약")]


def test_home_shows_today_highlight(client, monkeypatch):
    # 최신 데일리 하이라이트: 날짜 + 제목 + '전체 보기' 링크
    monkeypatch.setattr(webapp.render, "list_dailies", _dailies)
    body = client.get("/").get_data(as_text=True)
    assert 'class="today-banner"' in body
    assert "2026-07-08" in body
    assert "오늘의 AI 요약" in body
    assert 'href="/daily/2026-07-08"' in body
    assert "전체 보기" in body


def test_home_no_highlight_without_dailies(client, monkeypatch):
    # 데일리가 없으면 하이라이트 생략, 주제 그리드는 유지
    from web import render
    monkeypatch.setattr(webapp.render, "list_dailies", lambda: [])
    monkeypatch.setattr(webapp.render, "list_topics",
                        lambda: [render.TopicCard(name="주제A", count="3건")])
    body = client.get("/").get_data(as_text=True)
    assert 'class="today-banner"' not in body
    assert 'class="grid"' in body
    assert "주제A" in body


def test_home_topic_grid_still_rendered_with_highlight(client, monkeypatch):
    # 하이라이트가 있어도 주제 그리드는 그대로 렌더된다
    from web import render
    monkeypatch.setattr(webapp.render, "list_dailies", _dailies)
    monkeypatch.setattr(webapp.render, "list_topics",
                        lambda: [render.TopicCard(name="주제A", count="3건"),
                                 render.TopicCard(name="주제B", count="5건")])
    body = client.get("/").get_data(as_text=True)
    assert 'class="grid"' in body
    assert "주제A" in body and "주제B" in body
