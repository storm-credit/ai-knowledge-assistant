"""모델 doc 변경 감시기 (docs/15).

Claude·OpenAI·Gemini의 릴리스노트/changelog를 fetch → 이전 스냅샷과 diff →
바뀐 게 있으면 LLM으로 "무엇이 바뀌었나(개발자 관점)"를 요약해 notes/model-updates/에 쌓는다.

- 스냅샷은 요약 성공 후에만 갱신 → 쿼터 소진/실패 시 다음 실행에 재시도 (놓침 방지).
- 첫 실행은 baseline만 저장(LLM 0콜). 변경 없으면 0콜.
- LLM엔 diff만 주고 지어내기 금지.
"""
import difflib
import os
import re

import yaml

from .llm import QuotaExhausted, complete_text

CONFIG = "model_docs.yaml"
SNAP_DIR = "state/model_docs"
OUT_DIR = "notes/model-updates"
MIN_LEN = 200          # 이보다 짧으면 JS 전용 페이지로 보고 skip
DIFF_CAP = 4000        # LLM에 넘기는 diff 상한 (쿼터 폭주 방지)

WATCH_PROMPT = (
    "다음은 {provider} 모델 문서의 변경 diff다('+'=추가, '-'=삭제 줄). "
    "개발자 관점에서 무엇이 추가·변경·폐기됐는지 한국어 불릿으로 정리하라.\n"
    "- 새 모델·기능·파라미터·가격·폐기(deprecation)를 우선한다.\n"
    "- 우리 시스템(Gemini API·flash-lite 사용)에 영향이 있으면 항목 끝에 '(영향)'을 붙여라.\n"
    "- diff에 없는 내용은 절대 지어내지 마라. 광고·마케팅·내비게이션 문구는 무시하라.\n"
    "- 마크다운 헤딩('#')은 쓰지 말고 '- ' 불릿만 써라. 의미 있는 변경이 없으면 '- (특이사항 없음)'.\n\n"
    "diff:\n{diff}"
)

_TAG = re.compile(r"(?s)<[^>]+>")
_SCRIPT = re.compile(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>")
_WS = re.compile(r"\s+")
_UNSAFE = re.compile(r'[^0-9A-Za-z가-힣._-]+')


def _html_to_text(html: str) -> str:
    """HTML → 순수 텍스트 (script/style 제거, 태그 제거, 공백 정규화)."""
    html = _SCRIPT.sub(" ", html)
    html = _TAG.sub(" ", html)
    # 흔한 엔티티만 최소 처리
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&#39;", "'")):
        html = html.replace(a, b)
    return _WS.sub(" ", html).strip()


def diff_text(old: str, new: str) -> str:
    """줄 단위 unified diff에서 변경(+/-) 줄만 추린 텍스트. 변경 없으면 ''."""
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    changed = [ln for ln in difflib.unified_diff(old_lines, new_lines, lineterm="")
               if (ln.startswith("+") or ln.startswith("-"))
               and not ln.startswith(("+++", "---"))]
    return "\n".join(changed).strip()


def slug_for(provider: str, url: str) -> str:
    """URL별 스냅샷 파일명 (파일시스템 안전)."""
    tail = _UNSAFE.sub("_", url.split("://", 1)[-1])[:80].strip("_")
    return f"{_UNSAFE.sub('_', provider)}-{tail}"


def load_providers(config: str = CONFIG) -> list:
    try:
        with open(config, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except OSError:
        return []
    return [{"name": p["name"], "url": p["url"]}
            for p in (data.get("providers") or []) if p.get("name") and p.get("url")]


def summarize_change(provider: str, diff: str, client=None, clients=None,
                     model: str = "gemini-2.5-flash-lite") -> str:
    prompt = WATCH_PROMPT.format(provider=provider, diff=diff[:DIFF_CAP])
    return complete_text([{"role": "user", "content": prompt}],
                         client=client, clients=clients, model=model).strip()


def _default_fetch(url: str) -> str:
    import httpx
    r = httpx.get(url, follow_redirects=True, timeout=20,
                  headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.text


def run_watch(date: str, fetch=_default_fetch, client=None, clients=None,
              config: str = CONFIG, snap_dir: str = SNAP_DIR, out_dir: str = OUT_DIR,
              model: str = "gemini-2.5-flash-lite", min_len: int = MIN_LEN):
    """감시 1회. 변경 요약 섹션들을 notes/model-updates/{date}.md에 쓰고 경로 반환.
    변경/새 요약이 하나도 없으면 파일을 만들지 않고 None."""
    providers = load_providers(config)
    sections = []
    for p in providers:
        name, url = p["name"], p["url"]
        try:
            text = _html_to_text(fetch(url))
        except Exception as e:                       # URL별 실패 격리
            print(f"[skip] {name} doc fetch 실패: {str(e)[:60]}")
            continue
        if len(text) < min_len:                      # JS 전용/에러 페이지 방어
            print(f"[skip] {name} 텍스트 too short({len(text)}) — SPA 의심")
            continue
        os.makedirs(snap_dir, exist_ok=True)
        snap = os.path.join(snap_dir, slug_for(name, url) + ".txt")
        if not os.path.exists(snap):                 # 첫 실행: baseline만
            with open(snap, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"[watch] {name} baseline 저장")
            continue
        with open(snap, encoding="utf-8") as f:
            old = f.read()
        diff = diff_text(old, text)
        if not diff:                                 # 변경 없음: LLM 0콜
            continue
        try:
            summary = summarize_change(name, diff, client=client, clients=clients, model=model)
        except QuotaExhausted as e:                  # 쿼터 소진 → 스냅샷 유지, 다음에 재시도
            print(f"[retry-later] {name} 요약 보류(쿼터): {str(e)[:50]}")
            continue
        except Exception as e:
            print(f"[retry-later] {name} 요약 실패: {str(e)[:60]}")
            continue
        sections.append(f"## {name}\n출처: {url}\n\n{summary}\n")
        with open(snap, "w", encoding="utf-8") as f:  # 요약 성공 후에만 갱신
            f.write(text)
        print(f"[watch] {name} 변경 감지 → 요약")

    if not sections:
        return None
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{date}.md")
    header = f"# {date} 모델 업데이트\n\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(sections))
    print(f"[watch] {len(sections)}건 변경 → {path}")
    return path
