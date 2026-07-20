"""웹 /ask 라우트 — qa.answer는 모킹(라우트·렌더·이스케이프만 검증)."""
from web import app as webapp


def test_ask_form_get_no_query():
    body = webapp.app.test_client().get("/ask").get_data(as_text=True)
    assert 'name="q"' in body                     # 질문 폼 존재
    assert "답변" not in body or "answer" not in body.lower()


def test_ask_renders_answer_and_sources(monkeypatch):
    monkeypatch.setattr(webapp.qa, "answer", lambda q, **k: {
        "answer": "HBM 가격이 급등했습니다.",
        "sources": [{"title": "AI 모델·기술", "href": "/topic/AI", "kind": "topic"}],
        "grounded": True})
    body = webapp.app.test_client().get("/ask?q=메모리").get_data(as_text=True)
    assert "HBM 가격이 급등했습니다." in body
    assert 'href="/topic/AI"' in body and "AI 모델·기술" in body


def test_ask_escapes_query_and_answer(monkeypatch):
    # XSS: 질문·답변에 raw HTML이 있어도 이스케이프돼야 (|safe 미사용)
    monkeypatch.setattr(webapp.qa, "answer", lambda q, **k: {
        "answer": "<script>alert(1)</script>", "sources": [], "grounded": True})
    body = webapp.app.test_client().get("/ask?q=<img src=x onerror=1>").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in body
    assert "<img src=x onerror=1>" not in body
    assert "&lt;script&gt;" in body


def test_ask_handles_quota_exhausted(monkeypatch):
    from collector.llm import QuotaExhausted
    def boom(q, **k): raise QuotaExhausted("소진")
    monkeypatch.setattr(webapp.qa, "answer", boom)
    body = webapp.app.test_client().get("/ask?q=메모리").get_data(as_text=True)
    assert "쿼터" in body                          # 안내 문구, 500 아님
