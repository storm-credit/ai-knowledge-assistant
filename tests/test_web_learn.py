"""웹 뷰어 /learn — 학습 노트 목록·상세."""
from pathlib import Path

from web import render


def _write(dir_: Path, name: str, text: str) -> None:
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / name).write_text(text, encoding="utf-8")


NOTE = ("# 하네스 엔지니어링\n\n> 생성일 2026-07-03 · 적용형 학습 노트\n\n"
        "## 이게 뭔가\n에이전트 실행 틀. \n\n## 관련\n[[AI 모델·기술]]\n")


def test_list_learn_notes_newest_first(tmp_path):
    _write(tmp_path, "하네스 엔지니어링.md", NOTE)
    _write(tmp_path, "MCP.md", "# MCP\n\n> 생성일 2026-07-01\n\n본문\n")
    import os, time
    old = tmp_path / "MCP.md"
    os.utime(old, (time.time() - 1000, time.time() - 1000))   # MCP를 과거로
    entries = render.list_learn_notes(tmp_path)
    assert [e.name for e in entries] == ["하네스 엔지니어링", "MCP"]
    assert entries[0].title == "하네스 엔지니어링"


def test_list_learn_notes_empty_dir_ok(tmp_path):
    assert render.list_learn_notes(tmp_path / "none") == []


def test_load_learn_note_renders(tmp_path):
    _write(tmp_path, "하네스 엔지니어링.md", NOTE)
    title, html = render.load_learn_note("하네스 엔지니어링", tmp_path)
    assert title == "하네스 엔지니어링"
    assert "<h2>이게 뭔가</h2>" in html
    assert 'href="/topic/' in html   # [[위키링크]] 동작


def test_load_learn_note_rejects_traversal(tmp_path):
    assert render.load_learn_note("../secret", tmp_path) is None
    assert render.load_learn_note("a/b", tmp_path) is None


def test_learn_routes(tmp_path, monkeypatch):
    from web import app as webapp
    _write(tmp_path, "MCP.md", "# MCP\n\n본문\n")
    monkeypatch.setattr(webapp.render, "LEARN_DIR", tmp_path)
    client = webapp.app.test_client()
    body = client.get("/learn").get_data(as_text=True)
    assert "MCP" in body
    assert client.get("/learn/MCP").status_code == 200
    assert client.get("/learn/없는노트").status_code == 404
