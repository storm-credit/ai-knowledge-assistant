import pytest
from collector.summarize import complete_text


class FakeResp:
    def __init__(self, c): self.choices = [type("C", (), {"message": type("M", (), {"content": c})})]


class FakeClient:
    def __init__(self, c): self._c = c; self.chat = type("Ch", (), {"completions": self})()
    def create(self, **k): return FakeResp(self._c)


class Quota429Client:
    def __init__(self): self.chat = type("Ch", (), {"completions": self})()
    def create(self, **k): raise Exception("Error code: 429 - RESOURCE_EXHAUSTED quota exceeded")


def test_complete_text_returns_response_text():
    out = complete_text([{"role": "user", "content": "hi"}], client=FakeClient("응답 본문"))
    assert out == "응답 본문"


def test_complete_text_rotates_on_quota():
    out = complete_text([{"role": "user", "content": "hi"}],
                        clients=[Quota429Client(), FakeClient("두번째 성공")])
    assert out == "두번째 성공"


def test_complete_text_raises_last_when_all_exhausted():
    with pytest.raises(Exception) as ei:
        complete_text([{"role": "user", "content": "hi"}],
                      clients=[Quota429Client(), Quota429Client()])
    assert "429" in str(ei.value)


def test_complete_text_no_candidates_raises_runtimeerror():
    with pytest.raises(RuntimeError):
        complete_text([{"role": "user", "content": "hi"}], clients=[])


def test_complete_text_non_quota_error_propagates_immediately():
    class BoomClient:
        def __init__(s): s.chat = type("Ch", (), {"completions": s})()
        def create(s, **k): raise ValueError("boom")
    with pytest.raises(ValueError):
        complete_text([{"role": "user", "content": "hi"}], client=BoomClient())
