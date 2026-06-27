import os
from .models import Item

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"

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

PROMPT = (
    "다음 콘텐츠를 한국어로 3줄 이내로 핵심만 요약하고, 마지막 줄에 "
    "관련 주제 태그를 #해시태그 형식으로 3개 이하 붙여라. "
    "원문에 있는 내용만 사용하고, 없는 사실은 절대 지어내지 마라.\n\n"
    "제목: {title}\n출처: {source}\n내용:\n{body}"
)

def summarize_item(item: Item, client=None, model: str = "gemini-2.5-flash-lite",
                   clients=None) -> Item:
    body = (item.raw_text or item.title)[:6000]
    messages = [{"role": "user", "content": PROMPT.format(
        title=item.title, source=item.source_name, body=body)}]
    # 후보 키(클라이언트): 주입 client 우선(테스트) → clients → 환경의 모든 키
    if client is not None:
        candidates = [client]
    elif clients is not None:
        candidates = clients
    else:
        candidates = _default_clients()
    if not candidates:
        raise RuntimeError("GEMINI_API_KEY가 없습니다 (.env 확인)")

    last_err = None
    for c in candidates:
        try:
            resp = c.chat.completions.create(model=model, messages=messages)
            item.summary = resp.choices[0].message.content.strip()
            return item
        except Exception as e:
            last_err = e
            if _is_quota_error(e):
                continue          # 쿼터 초과 → 다음 키로 로테이션
            raise                 # 다른 에러는 즉시 중단
    raise last_err                # 모든 키가 쿼터 초과
