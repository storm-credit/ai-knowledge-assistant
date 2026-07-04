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
