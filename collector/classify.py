from typing import List
from .models import Item
from .summarize import _default_clients, _is_quota_error

CLASSIFY_PROMPT = (
    "다음 글을 1~3개의 주제로 분류해라. 기존 주제 목록에 맞는 게 있으면 가능한 그 중에서 고르고, "
    "없으면 새 주제명을 만들어라. 주제명은 짧은 한국어 명사구. "
    "쉼표로 구분해 주제명만 출력해라(설명·번호 금지).\n\n"
    "기존 주제: {known}\n제목: {title}\n요약: {summary}"
)

def classify_item(item: Item, known_topics: List[str], client=None, clients=None,
                  model: str = "gemini-2.5-flash-lite") -> List[str]:
    prompt = CLASSIFY_PROMPT.format(
        known=", ".join(known_topics) or "(없음)",
        title=item.title, summary=item.summary or item.raw_text[:500])
    cands = [client] if client is not None else (clients if clients is not None else _default_clients())
    last = None
    for c in cands:
        try:
            resp = c.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}])
            text = resp.choices[0].message.content.strip()
            parts = [p.strip().lstrip("#").strip() for p in text.replace("\n", ",").split(",")]
            return [p for p in parts if p][:3]
        except Exception as e:
            last = e
            if _is_quota_error(e):
                continue
            raise
    raise last
