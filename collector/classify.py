from typing import List
from .models import Item
from .summarize import _default_clients, _is_quota_error

CATEGORIES = ["AI 모델·기술", "AI 비즈니스·투자", "AI 활용·도구",
              "한국 AI·스타트업", "인프라·에너지", "인재·일의 미래", "기타"]

CLASSIFY_PROMPT = (
    "다음 카테고리 중 가장 맞는 것 1개(최대 2개)만 골라라. 목록에 없으면 '기타'. "
    "카테고리명만 쉼표로 출력.\n\n"
    "카테고리: {categories}\n제목: {title}\n요약: {summary}"
)

def classify_item(item: Item, known_topics: List[str], client=None, clients=None,
                  model: str = "gemini-2.5-flash-lite") -> List[str]:
    categories = known_topics or CATEGORIES
    prompt = CLASSIFY_PROMPT.format(
        categories=", ".join(categories),
        title=item.title, summary=item.summary or item.raw_text[:500])
    cands = [client] if client is not None else (clients if clients is not None else _default_clients())
    last = None
    for c in cands:
        try:
            resp = c.chat.completions.create(
                model=model, messages=[{"role": "user", "content": prompt}])
            text = resp.choices[0].message.content.strip()
            parts = [p.strip().lstrip("#").strip() for p in text.replace("\n", ",").split(",")]
            valid = [p for p in parts if p in CATEGORIES][:2]
            return valid or ["기타"]
        except Exception as e:
            last = e
            if _is_quota_error(e):
                continue
            raise
    raise last
