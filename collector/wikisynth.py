import json, re
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
    if not cands:
        raise RuntimeError("GEMINI_API_KEY가 없습니다 (.env 확인)")
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
    "아래 형태의 JSON만 출력하라(설명·코드펜스·다른 텍스트 금지):\n"
    '{{"overview": "3~4문장 한국어 개요",\n'
    ' "themes": [{{"name": "테마이름", "intro": "1~2문장 정리", "items": [1,3]}}],\n'
    ' "orphans": [4],\n'
    ' "related": ["Claude","GPU"]}}\n'
    "규칙:\n"
    "- 항목은 번호로만 가리킬 것. items/orphans는 항목 번호의 정수 배열.\n"
    "- 테마는 2~4개로 묶어라.\n"
    "- 어느 테마에도 안 맞는 항목은 orphans에 넣어라.\n"
    "- URL은 쓰지 마라. 원문에 없는 사실은 지어내지 마라.\n"
    "- JSON만 출력하라.\n\n"
    "항목들:\n{items}"
)

def _ints(seq):
    out = []
    for v in (seq or []):
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            continue
    return out

def _parse_struct_json(text: str) -> dict:
    """응답에서 코드펜스/공백을 벗기고 JSON을 파싱해 표준 구조로 변환.
    실패하거나 키가 없으면 빈 구조를 반환(호출부가 가드)."""
    empty = {"overview": "", "themes": [], "orphans": [], "related": []}
    s = (text or "").strip()
    # 펜스 제거 (열고 닫는 쌍이 안 맞아도 각각 독립적으로 제거)
    s = re.sub(r'^```(?:json)?\s*', '', s)
    s = re.sub(r'\s*```$', '', s)
    s = s.strip()
    try:
        data = json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return empty
    if not isinstance(data, dict):
        return empty
    overview = data.get("overview")
    themes_in = data.get("themes")
    if not isinstance(overview, str) or not isinstance(themes_in, list):
        return empty
    themes = []
    for th in themes_in[:4]:
        if not isinstance(th, dict):
            continue
        name = th.get("name")
        if not isinstance(name, str) or not name:
            continue
        themes.append({"name": name, "intro": th.get("intro", "") if isinstance(th.get("intro"), str) else "",
                       "indexes": _ints(th.get("items"))})
    related = [x.strip().lstrip("#").strip()
               for x in (data.get("related") or []) if isinstance(x, str) and x.strip()]
    return {"overview": overview, "themes": themes,
            "orphans": _ints(data.get("orphans")), "related": related[:4]}

def synthesize_structure(topic: str, items: List[dict], client=None, clients=None,
                         model: str = "gemini-2.5-flash-lite") -> dict:
    numbered = "\n".join(f"[{i+1}] {it.get('title','')} — {it.get('summary','')}"
                         for i, it in enumerate(items))[:8000]
    prompt = SYNTH_STRUCT_PROMPT.format(topic=topic, items=numbered)
    cands = [client] if client is not None else (clients if clients is not None else _default_clients())
    if not cands:
        raise RuntimeError("GEMINI_API_KEY가 없습니다 (.env 확인)")
    last = None
    for c in cands:
        try:
            resp = c.chat.completions.create(model=model, messages=[{"role":"user","content":prompt}])
            text = resp.choices[0].message.content.strip()
            return _parse_struct_json(text)
        except Exception as e:
            last = e
            if _is_quota_error(e):
                continue
            raise
    raise last
