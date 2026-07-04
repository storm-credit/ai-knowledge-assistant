"""LLM 게이트웨이 — 모든 Gemini 호출이 여기를 거친다.

- 키 로테이션 (429 → 다음 키)
- 일일 콜 예산 (state/llm_budget.json, 기본 18콜)
- 서킷브레이커 (한 실행에서 전 키 429 소진 시 이후 호출 즉시 차단)
- 503/과부하 일시 오류는 같은 키에서 짧은 backoff 후 재시도
"""
import datetime
import json
import os
import time

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"


class QuotaExhausted(RuntimeError):
    """일일 예산 소진 또는 전 키 429 소진. 호출부는 기존 [retry-later]/[skip] 경로로 처리."""


def _collect_keys():
    """현재 환경에서 GEMINI_API_KEY 및 GEMINI_API_KEY_1.._N 수집 (빈 값 제외, 중복 제거)."""
    candidates = [os.environ.get("GEMINI_API_KEY")]
    for i in range(1, 11):
        candidates.append(os.environ.get(f"GEMINI_API_KEY_{i}"))
    keys, seen = [], set()
    for v in candidates:
        if v and v.strip() and v.strip() not in seen:
            seen.add(v.strip())
            keys.append(v.strip())
    return keys


def _api_keys():
    """프로젝트 .env의 키를 우선 사용. 거기에 하나도 없을 때만 Hermes .env로 폴백
    (= 프로젝트에 키가 있으면 Hermes와 완전 분리)."""
    try:
        from dotenv import load_dotenv
        load_dotenv()                    # 프로젝트 .env
        keys = _collect_keys()
        if not keys:
            load_dotenv(os.path.expanduser("~/.hermes/.env"))  # 폴백만
            keys = _collect_keys()
        return keys
    except ImportError:
        return _collect_keys()


def _default_clients():
    from openai import OpenAI
    return [OpenAI(api_key=k, base_url=GEMINI_BASE) for k in _api_keys()]


def _is_quota_error(e) -> bool:
    s = str(e).lower()
    return "429" in s or "resource_exhausted" in s or "quota" in s


def _is_overload_error(e) -> bool:
    """503/과부하 계열 일시 오류 감지 (429 쿼터와 별개 — 같은 키 재시도 대상)."""
    s = str(e).lower()
    return "503" in s or "overloaded" in s or "unavailable" in s


class CallBudget:
    """일일 LLM 콜 예산. {"date","calls"}를 JSON 파일에 저장, 날짜가 바뀌면 자동 리셋."""

    def __init__(self, path: str = "state/llm_budget.json", limit: int = 18, today=None):
        self.path = path
        self.limit = limit
        self._today = today or (lambda: datetime.date.today().isoformat())
        self.date = self._today()
        self.calls = 0
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("date") == self.date:   # 다른 날짜면 0에서 시작 (리셋)
                self.calls = int(data.get("calls", 0))
        except (OSError, ValueError, TypeError):
            pass

    def _roll(self) -> None:
        t = self._today()
        if t != self.date:   # 실행 중 자정을 넘겨도 리셋
            self.date, self.calls = t, 0

    def exhausted(self) -> bool:
        self._roll()
        return self.calls >= self.limit

    def record_call(self) -> None:
        """성공 콜 1회 기록 + 즉시 저장 (크래시에도 카운트 보존)."""
        self._roll()
        self.calls += 1
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"date": self.date, "calls": self.calls}, f)


class CircuitBreaker:
    """한 실행(프로세스) 안에서 전 키가 429로 소진되면 이후 API 호출을 즉시 차단."""

    def __init__(self):
        self.tripped = False

    def trip(self) -> None:
        self.tripped = True

    def reset(self) -> None:
        self.tripped = False


# 실제 실행(클라이언트 미주입) 경로에서만 쓰는 모듈 기본 예산·브레이커
_default_budget = None
_default_breaker = CircuitBreaker()


def _module_budget() -> CallBudget:
    global _default_budget
    if _default_budget is None:
        _default_budget = CallBudget()
    return _default_budget


def _create_with_overload_retry(c, model, messages, sleep, backoff, retries, **create_kwargs) -> str:
    """한 클라이언트(키)로 호출. 503/과부하면 backoff 후 같은 키로 재시도 (429 로테이션과 분리)."""
    for attempt in range(retries + 1):
        try:
            return c.chat.completions.create(model=model, messages=messages,
                                             **create_kwargs).choices[0].message.content or ""
        except Exception as e:
            if _is_overload_error(e) and not _is_quota_error(e) and attempt < retries:
                sleep(backoff)
                continue
            raise


def complete_text(messages, client=None, clients=None, model: str = "gemini-2.5-flash-lite",
                  budget=None, breaker=None,
                  sleep=time.sleep, overload_backoff: float = 2.0,
                  overload_retries: int = 2, **create_kwargs) -> str:
    """키 로테이션으로 chat completion을 실행하고 응답 텍스트를 반환한다.
    후보 클라이언트: 주입 client 우선 → clients → 환경의 모든 키. 후보가 비면 RuntimeError.
    - 429: 다음 키로 로테이션. 전 키 소진 시 QuotaExhausted + 서킷브레이커 작동.
    - 503/과부하: 같은 키에서 backoff 후 재시도. 다른 에러는 즉시 전파.
    - 예산·브레이커는 클라이언트 미주입(실제 실행) 시 모듈 기본값 적용, 파라미터로 주입 가능.
    - 추가 kwargs(response_format 등)는 create()로 그대로 전달."""
    injected = client is not None or clients is not None
    if budget is None and not injected:
        budget = _module_budget()
    if breaker is None and not injected:
        breaker = _default_breaker
    if breaker is not None and breaker.tripped:
        raise QuotaExhausted("서킷브레이커 작동: 이번 실행에서 전 키 429 소진됨")
    if budget is not None and budget.exhausted():
        raise QuotaExhausted(f"일일 콜 예산 소진 ({budget.calls}/{budget.limit})")

    if client is not None:
        cands = [client]
    elif clients is not None:
        cands = clients
    else:
        cands = _default_clients()
    if not cands:
        raise RuntimeError("GEMINI_API_KEY가 없습니다 (.env 확인)")
    last = None
    for c in cands:
        try:
            text = _create_with_overload_retry(c, model, messages, sleep,
                                               overload_backoff, overload_retries,
                                               **create_kwargs)
        except Exception as e:
            last = e
            if _is_quota_error(e):
                continue
            raise
        if budget is not None:
            budget.record_call()
        return text
    if breaker is not None:
        breaker.trip()
    raise QuotaExhausted(f"전 키 쿼터 소진: {last}")
