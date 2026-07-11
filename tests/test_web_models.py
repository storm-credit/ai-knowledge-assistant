"""웹 /models — 모델 업데이트 목록·상세."""
from pathlib import Path

from web import render


def _write(dir_: Path, name: str, text: str) -> None:
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / name).write_text(text, encoding="utf-8")


NOTE = ("# 2026-07-11 모델 업데이트\n\n## Gemini\n출처: http://x\n\n"
        "- Gemini 3.0 출시 (영향)\n")


def test_list_model_updates_newest_first(tmp_path):
    _write(tmp_path, "2026-07-10.md", "# 2026-07-10 모델 업데이트\n\n## OpenAI\n- x\n")
    _write(tmp_path, "2026-07-11.md", NOTE)
    _write(tmp_path, "notes.md", "# stray\n")   # 날짜 아님 → 무시
    entries = render.list_model_updates(tmp_path)
    assert [e.date for e in entries] == ["2026-07-11", "2026-07-10"]


def test_list_model_updates_empty_dir_ok(tmp_path):
    assert render.list_model_updates(tmp_path / "none") == []


def test_load_model_update_renders(tmp_path):
    _write(tmp_path, "2026-07-11.md", NOTE)
    title, html = render.load_model_update("2026-07-11", tmp_path)
    assert "2026-07-11" in title
    assert "<h2>Gemini</h2>" in html
    assert "Gemini 3.0" in html


def test_load_model_update_validates_date(tmp_path):
    _write(tmp_path, "2026-07-11.md", NOTE)
    assert render.load_model_update("2026-07-11", tmp_path) is not None
    assert render.load_model_update("bad", tmp_path) is None
    assert render.load_model_update("../secret", tmp_path) is None


def test_models_routes(tmp_path, monkeypatch):
    from web import app as webapp
    _write(tmp_path, "2026-07-11.md", NOTE)
    monkeypatch.setattr(webapp.render, "MODEL_UPDATES_DIR", tmp_path)
    client = webapp.app.test_client()
    body = client.get("/models").get_data(as_text=True)
    assert "2026-07-11" in body
    assert client.get("/models/2026-07-11").status_code == 200
    assert client.get("/models/2026-99-99").status_code == 404
    assert client.get("/models/bad").status_code == 404
