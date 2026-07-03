"""적용형 학습 노트 (docs/14) — 개념 하나를 정리+학습경로+내 적용법으로.

학습 카드(요약)와 달리 독립 페이지(notes/learn/)라 헤딩을 자유롭게 쓴다.
섹션별 근거 규칙(grounded/generative 분리):
- 이게 뭔가·관련: 피드 맥락 + 일반지식 허용, 불확실한 부분은 (불확실) 표시
- 어떻게 배우나: 일반지식 허용
- 내 적용법: 프로필(notes/me.md) 기반 추론 허용, 각 제안에 (제안) 표시
"""
import os
import re

from .llm import CallBudget, complete_text
from .store import load_items
from .topics import TopicStore

PROFILE_PATH = "notes/me.md"
OUT_DIR = "notes/learn"
MIN_REMAINING = 2   # 예산 잔여가 이보다 적으면 미룸 — 본업(아침 수집)이 우선

LEARN_PROMPT = (
    "'{concept}'에 대한 한국어 '학습 노트'를 작성하라.\n"
    "정확히 아래 4개 섹션을 '## ' 헤딩으로 구성하고, 다른 섹션은 만들지 마라:\n\n"
    "## 이게 뭔가\n"
    "개념 정의와 왜 지금 화제인지 3~5문장. "
    "일반 지식을 써도 되지만, 확실하지 않거나 최신 변화가 있을 수 있는 내용 뒤에는 '(불확실)'을 붙여라. "
    "생소한 신조어라 여러 해석이 가능하면 아는 척 단정하지 말고 가장 유력한 해석을 제시하며 '(불확실)'을 명시하라. "
    "아래 '내 피드 맥락'은 참고일 뿐이다 — 판촉 문구(쿠폰·할인·수강 등)가 섞여 있거나 개념 설명과 무관해 보이면 무시하라.\n\n"
    "## 어떻게 배우나\n"
    "배우는 순서 3~5단계 불릿. 각 단계는 무엇을 왜 먼저 하는지 한 줄씩, 실습 위주로.\n\n"
    "## 내 적용법\n"
    "아래 내 프로필을 근거로 '너는 X를 하니까 이렇게 써먹어라' 식의 구체 제안 2~4개 불릿. "
    "이 섹션은 추론이므로 각 제안 끝에 '(제안)'을 붙여라. "
    "프로필이 '(프로필 없음)'이면 일반적인 실무 적용 예를 들어라.\n\n"
    "## 관련\n"
    "아래 '내 위키 주제' 중 관련 있는 것만 [[주제명]] 형식으로 한 줄에 나열. 없으면 '없음'.\n\n"
    "규칙: 광고·판촉·구독 권유 금지. 지어낸 출처·URL 금지. 밀도 있게 400~700자.\n\n"
    "내 프로필:\n{profile}\n\n"
    "내 피드 맥락(최근 수집 항목 중 관련):\n{context}\n\n"
    "내 위키 주제: {topics}"
)


def load_profile(path: str = PROFILE_PATH) -> str:
    """notes/me.md 프로필. 없거나 비어 있어도 동작한다 (그땐 일반 적용법)."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            return f.read().strip()
    except OSError:
        return ""


def find_feed_context(concept: str, items_store: str = "state/items.jsonl",
                      limit: int = 5) -> list:
    """최근 수집 항목에서 개념이 언급된 것을 찾아 프롬프트용 블록으로 (LLM 콜 없음)."""
    needle = concept.lower()
    out = []
    for it in reversed(load_items(items_store)):   # 최신 우선
        hay = f"{it.title}\n{it.summary}".lower()
        if needle in hay:
            summ = (it.summary or "").strip().replace("\n", " ")[:250]
            out.append(f"- [{it.title}] ({it.source_name}, {it.published[:10]}) {summ}")
            if len(out) >= limit:
                break
    return out


def build_prompt(concept: str, profile: str, context: list, topics: list) -> str:
    return LEARN_PROMPT.format(
        concept=concept,
        profile=profile.strip() or "(프로필 없음)",
        context="\n".join(context) or "(관련 피드 항목 없음)",
        topics=", ".join(topics) or "(없음)")


def compose_note(concept: str, body: str, date: str) -> str:
    """LLM 출력 앞에 제목·생성일을 붙여 완성된 노트로. 모델이 넣은 중복 h1은 제거."""
    lines = [ln for ln in body.strip().splitlines()
             if not (ln.startswith("# ") and not ln.startswith("## "))]
    return (f"# {concept}\n\n> 생성일 {date} · 적용형 학습 노트\n\n"
            + "\n".join(lines).strip() + "\n")


def note_filename(concept: str) -> str:
    """topics.write_pages와 동일한 금지문자 치환 규칙."""
    safe = re.sub(r'[\\/:*?"<>|]', "_", concept).strip() or "untitled"
    return f"{safe}.md"


def run_learn(concept: str, date: str, client=None, clients=None, budget=None,
              items_store: str = "state/items.jsonl",
              topics_path: str = "state/topics.json",
              profile_path: str = PROFILE_PATH,
              out_dir: str = OUT_DIR,
              model: str = "gemini-2.5-flash-lite"):
    """학습 노트 1건 생성 (LLM 1콜). 예산 잔여 < MIN_REMAINING이면 미루고 None."""
    injected = client is not None or clients is not None
    if budget is None and not injected:
        budget = CallBudget()
    if budget is not None:
        budget.exhausted()   # 날짜 롤 반영
        remaining = budget.limit - budget.calls
        if remaining < MIN_REMAINING:
            print(f"[skip] 예산 잔여 {remaining}콜 < {MIN_REMAINING} — 학습 노트는 다음에")
            return None

    profile = load_profile(profile_path)
    context = find_feed_context(concept, items_store=items_store)
    topics = TopicStore(topics_path).topic_names()
    prompt = build_prompt(concept, profile, context, topics)
    body = complete_text([{"role": "user", "content": prompt}],
                         client=client, clients=clients, model=model,
                         budget=budget if not injected else None)
    note = compose_note(concept, body, date=date)

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, note_filename(concept))
    with open(path, "w", encoding="utf-8") as f:
        f.write(note)
    print(f"[learn] {concept} → {path}")
    return path
