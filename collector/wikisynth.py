from typing import List, Tuple
from .summarize import _default_clients, _is_quota_error

SYNTH_PROMPT = (
    "다음은 '{topic}' 주제로 모인 항목들이다. 이를 바탕으로 한국어로 정리하라.\n"
    "1) 첫 줄에 '개요: '로 시작해 3~5문장 요약.\n"
    "2) 다음 줄에 '관련주제: '로 시작해 관련될 만한 다른 주제 2~4개를 쉼표로.\n"
    "원문에 없는 사실은 지어내지 마라.\n\n항목들:\n{items}"
)

def synthesize_overview(topic: str, items: List[dict], client=None, clients=None,
                        model: str = "gemini-2.5-flash-lite") -> Tuple[str, List[str]]:
    body = "\n".join(f"- {i.get('title','')}: {i.get('summary','')}" for i in items)[:8000]
    prompt = SYNTH_PROMPT.format(topic=topic, items=body)
    cands = [client] if client is not None else (clients if clients is not None else _default_clients())
    last = None
    for c in cands:
        try:
            resp = c.chat.completions.create(model=model, messages=[{"role":"user","content":prompt}])
            text = resp.choices[0].message.content.strip()
            overview, related = "", []
            for line in text.splitlines():
                s = line.strip()
                if s.startswith("개요:"):
                    overview = s[len("개요:"):].strip()
                elif s.startswith("관련주제:"):
                    related = [x.strip().lstrip("#").strip()
                               for x in s[len("관련주제:"):].split(",") if x.strip()]
            if not overview:
                overview = text   # 형식 안 맞으면 통째로
            return overview, related[:4]
        except Exception as e:
            last = e
            if _is_quota_error(e):
                continue
            raise
    raise last
