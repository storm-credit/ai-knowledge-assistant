import json
import pytest
from collector.llm import (CallBudget, CircuitBreaker, QuotaExhausted,
                           complete_text, _is_overload_error)


class FakeResp:
    def __init__(self, c): self.choices = [type("C", (), {"message": type("M", (), {"content": c})})]


class FakeClient:
    """성공 응답 + 호출 횟수 기록."""
    def __init__(self, c="응답"): self._c = c; self.calls = 0; self.chat = type("Ch", (), {"completions": self})()
    def create(self, **k):
        self.calls += 1
        return FakeResp(self._c)


class Quota429Client:
    def __init__(self): self.calls = 0; self.chat = type("Ch", (), {"completions": self})()
    def create(self, **k):
        self.calls += 1
        raise Exception("Error code: 429 - RESOURCE_EXHAUSTED quota exceeded")


class Overload503Client:
    """처음 fail_n번은 503, 그 다음부터 성공."""
    def __init__(self, fail_n, c="복구됨"):
        self.fail_n = fail_n; self._c = c; self.calls = 0
        self.chat = type("Ch", (), {"completions": self})()
    def create(self, **k):
        self.calls += 1
        if self.calls <= self.fail_n:
            raise Exception("Error code: 503 - The model is overloaded")
        return FakeResp(self._c)


MSGS = [{"role": "user", "content": "hi"}]


# ---------- CallBudget ----------

def test_budget_counts_successful_calls_and_persists(tmp_path):
    path = str(tmp_path / "budget.json")
    b = CallBudget(path, limit=5)
    complete_text(MSGS, client=FakeClient(), budget=b)
    complete_text(MSGS, client=FakeClient(), budget=b)
    assert b.calls == 2
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["calls"] == 2
    # 같은 날짜로 다시 로드하면 카운트 유지
    assert CallBudget(path, limit=5).calls == 2


def test_budget_resets_on_new_date(tmp_path):
    path = str(tmp_path / "budget.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"date": "2026-07-01", "calls": 17}, f)
    b = CallBudget(path, limit=18, today=lambda: "2026-07-02")
    assert b.calls == 0
    assert b.exhausted() is False


def test_budget_blocks_at_limit_without_api_call(tmp_path):
    path = str(tmp_path / "budget.json")
    b = CallBudget(path, limit=1)
    complete_text(MSGS, client=FakeClient(), budget=b)
    blocked = FakeClient()
    with pytest.raises(QuotaExhausted):
        complete_text(MSGS, client=blocked, budget=b)
    assert blocked.calls == 0   # 한도 도달 후에는 API를 때리지 않음


def test_budget_rolls_over_midprocess(tmp_path):
    day = {"v": "2026-07-01"}
    b = CallBudget(str(tmp_path / "budget.json"), limit=1, today=lambda: day["v"])
    complete_text(MSGS, client=FakeClient(), budget=b)
    assert b.exhausted() is True
    day["v"] = "2026-07-02"   # 자정 넘김
    assert b.exhausted() is False
    assert b.calls == 0


def test_failed_call_does_not_consume_budget(tmp_path):
    class Boom:
        def __init__(s): s.chat = type("Ch", (), {"completions": s})()
        def create(s, **k): raise ValueError("boom")
    b = CallBudget(str(tmp_path / "budget.json"), limit=5)
    with pytest.raises(ValueError):
        complete_text(MSGS, client=Boom(), budget=b)
    assert b.calls == 0


# ---------- 서킷브레이커 ----------

def test_breaker_trips_when_all_keys_429():
    br = CircuitBreaker()
    with pytest.raises(QuotaExhausted):
        complete_text(MSGS, clients=[Quota429Client(), Quota429Client()], breaker=br)
    assert br.tripped is True


def test_tripped_breaker_skips_api_immediately():
    br = CircuitBreaker()
    br.trip()
    c = FakeClient()
    with pytest.raises(QuotaExhausted):
        complete_text(MSGS, client=c, breaker=br)
    assert c.calls == 0   # API를 아예 안 때림


def test_all_429_raises_quota_exhausted_subclass():
    with pytest.raises(QuotaExhausted) as ei:
        complete_text(MSGS, clients=[Quota429Client()])
    assert isinstance(ei.value, RuntimeError)   # 기존 호출부 호환
    assert "429" in str(ei.value)


# ---------- 503 재시도 ----------

def test_overload_retries_same_key_with_backoff():
    c = Overload503Client(fail_n=2)
    sleeps = []
    out = complete_text(MSGS, client=c, sleep=sleeps.append, overload_backoff=2.0)
    assert out == "복구됨"
    assert c.calls == 3           # 실패 2번 + 성공 1번 (같은 키)
    assert sleeps == [2.0, 2.0]   # 재시도마다 backoff


def test_overload_exhausted_retries_propagates_without_rotation():
    always503 = Overload503Client(fail_n=99)
    other = FakeClient()
    with pytest.raises(Exception) as ei:
        complete_text(MSGS, clients=[always503, other],
                      sleep=lambda *_: None, overload_retries=2)
    assert "503" in str(ei.value)
    assert always503.calls == 3   # 1회 + 재시도 2회
    assert other.calls == 0       # 503은 키 로테이션 안 함 (429와 분리)


def test_is_overload_error_detection():
    assert _is_overload_error(Exception("Error code: 503 Service Unavailable"))
    assert _is_overload_error(Exception("The model is overloaded. Please try again"))
    assert _is_overload_error(Exception("UNAVAILABLE"))
    assert not _is_overload_error(Exception("429 RESOURCE_EXHAUSTED quota"))
    assert not _is_overload_error(Exception("boom"))


# ---------- 재수출 호환 ----------

def test_summarize_reexports_llm_symbols():
    import collector.summarize as s
    import collector.llm as llm
    assert s.complete_text is llm.complete_text
    assert s._is_quota_error is llm._is_quota_error
    assert s._collect_keys is llm._collect_keys
    assert s._api_keys is llm._api_keys
    assert s.GEMINI_BASE == llm.GEMINI_BASE


def test_classify_and_wikisynth_use_llm_gateway():
    import collector.classify as c
    import collector.wikisynth as w
    import collector.llm as llm
    assert c.complete_text is llm.complete_text
    assert w.complete_text is llm.complete_text
