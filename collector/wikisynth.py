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


SYNTH_STRUCT_PROMPT = (
    "다음은 '{topic}' 주제로 모인 항목들이다(번호 매김). 한국어로 정리하라.\n"
    "1) '개요: '로 시작해 3~4문장으로 이 분야의 큰 그림.\n"
    "2) 항목들을 2~4개 테마로 묶어라. 각 테마는 한 줄:\n"
    "   '[테마] 테마이름 || 1~2문장 정리 || 항목번호(쉼표)'\n"
    "3) 어느 테마에도 안 맞는 항목: '[단신] 항목번호(쉼표)'\n"
    "4) '관련주제: '로 시작해 관련 주제 2~4개를 쉼표로.\n"
    "원문에 없는 사실은 지어내지 마라. 항목은 번호로만 가리키고 URL은 쓰지 마라.\n\n"
    "항목들:\n{items}"
)

def _nums(s: str):
    out = []
    for tok in s.replace("，", ",").split(","):
        tok = tok.strip()
        if tok.isdigit():
            out.append(int(tok))
    return out

def synthesize_structure(topic: str, items: List[dict], client=None, clients=None,
                         model: str = "gemini-2.5-flash-lite") -> dict:
    numbered = "\n".join(f"[{i+1}] {it.get('title','')} — {it.get('summary','')}"
                         for i, it in enumerate(items))[:8000]
    prompt = SYNTH_STRUCT_PROMPT.format(topic=topic, items=numbered)
    cands = [client] if client is not None else (clients if clients is not None else _default_clients())
    last = None
    for c in cands:
        try:
            resp = c.chat.completions.create(model=model, messages=[{"role":"user","content":prompt}])
            text = resp.choices[0].message.content.strip()
            overview, themes, orphans, related = "", [], [], []
            for line in text.splitlines():
                s = line.strip()
                if s.startswith("개요:"):
                    overview = s[len("개요:"):].strip()
                elif s.startswith("[테마]"):
                    parts = [p.strip() for p in s[len("[테마]"):].split("||")]
                    name = parts[0] if parts else ""
                    intro = parts[1] if len(parts) > 1 else ""
                    idxs = _nums(parts[2]) if len(parts) > 2 else []
                    if name:
                        themes.append({"name": name, "intro": intro, "indexes": idxs})
                elif s.startswith("[단신]"):
                    orphans = _nums(s[len("[단신]"):])
                elif s.startswith("관련주제:"):
                    related = [x.strip().lstrip("#").strip()
                               for x in s[len("관련주제:"):].split(",") if x.strip()]
            return {"overview": overview, "themes": themes[:4],
                    "orphans": orphans, "related": related[:4]}
        except Exception as e:
            last = e
            if _is_quota_error(e):
                continue
            raise
    raise last
