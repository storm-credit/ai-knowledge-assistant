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

def complete_text(messages, client=None, clients=None, model: str = "gemini-2.5-flash-lite") -> str:
    """키 로테이션으로 chat completion을 실행하고 응답 텍스트를 반환한다.
    후보 클라이언트: 주입 client 우선 → clients → 환경의 모든 키.
    후보가 비면 RuntimeError. 쿼터 초과(429)면 다음 키로 로테이션, 다른 에러는 즉시 전파."""
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
            return c.chat.completions.create(model=model, messages=messages).choices[0].message.content or ""
        except Exception as e:
            last = e
            if _is_quota_error(e):
                continue
            raise
    raise last

SUMMARIZE_CLASSIFY_PROMPT = (
    "다음 콘텐츠를 한국어로 핵심 포인트 5~7개로 자세히 요약하라. "
    "각 포인트는 '- '로 시작하는 불릿 한 줄로, 구체적 사실·수치·맥락을 담아라(단순 한 줄 요약 금지). "
    "원문에 있는 내용만 사용하고, 없는 사실은 절대 지어내지 마라. "
    "그 다음 마지막 줄에 '카테고리: '로 시작해 아래 목록 중 가장 맞는 것 1개(최대 2개)만 쉼표로 적어라. "
    "목록에 없으면 '기타'.\n\n"
    "카테고리 목록: {categories}\n\n"
    "제목: {title}\n출처: {source}\n내용:\n{body}"
)

# 학습형 출처 전용. 위키의 ### 기사 밑에 그대로 삽입되므로 헤딩(#)을 쓰면
# 테마 구조가 깨진다 → 굵은 라벨 + 불릿 + 코드펜스만 쓰도록 강제.
LEARNING_PROMPT = (
    "다음은 개발·학습 콘텐츠다. 한국어로 '학습 카드'를 만들어라. "
    "원문에 있는 내용만 사용하고, 없는 사실·코드는 절대 지어내지 마라. "
    "아래 형식을 그대로 지켜라. 마크다운 헤딩('#')은 절대 쓰지 말고, 굵은 라벨과 불릿만 써라:\n\n"
    "**핵심 개념**\n- (배워야 할 개념·원리 3~5개, 각 한 줄)\n\n"
    "**코드·명령**\n(원문에 코드/명령/CLI가 있을 때만. ```로 감싼 코드펜스로 적어라. 없으면 이 섹션 전체를 생략)\n\n"
    "**실습 포인트**\n- (따라 할 수 있는 단계나 팁 2~4개)\n\n"
    "**한 줄 정리**\n(한 문장)\n\n"
    "그 다음 마지막 줄에 '카테고리: '로 시작해 아래 목록 중 1개(최대 2개)만 쉼표로 적어라. 없으면 '개발·학습'.\n"
    "카테고리 목록: {categories}\n\n"
    "제목: {title}\n출처: {source}\n내용:\n{body}"
)

DEV_CATEGORY = "개발·학습"

def summarize_and_classify(item: Item, client=None, model: str = "gemini-2.5-flash-lite",
                           clients=None, categories=None) -> Item:
    """요약과 카테고리 분류를 한 번의 LLM 호출로 처리한다 (호출 수 절감).

    학습형 항목(item.learning)은 LEARNING_PROMPT로 학습 카드를 만든다."""
    from .classify import load_categories
    cats = categories if categories is not None else load_categories()
    body = (item.raw_text or item.title)[:6000]
    prompt = LEARNING_PROMPT if item.learning else SUMMARIZE_CLASSIFY_PROMPT
    messages = [{"role": "user", "content": prompt.format(
        categories=", ".join(cats), title=item.title,
        source=item.source_name, body=body)}]
    text = complete_text(messages, client=client, clients=clients, model=model).strip()
    summary_lines, found = [], []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("카테고리:"):
            found = [x.strip().lstrip("#").strip()
                     for x in s[len("카테고리:"):].split(",")]
        else:
            summary_lines.append(line)
    item.summary = "\n".join(summary_lines).strip()
    valid = [p for p in found if p in cats][:2]
    if valid:
        item.categories = valid
    elif item.learning and DEV_CATEGORY in cats:
        item.categories = [DEV_CATEGORY]   # 학습 항목 기본 분류
    else:
        item.categories = ["기타"]
    return item
