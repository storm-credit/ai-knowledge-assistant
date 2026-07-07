"""요약·학습 카드 프롬프트 회귀 eval (docs/13 #13).

PLAYBOOK 7절 'AI 전문가 트랙': 프롬프트를 수정하면 이걸 수동 1회 돌려 품질 회귀를 잡는다.
평시 pytest·cron에서는 실행되지 않는다 (환경변수 게이트).

    RUN_LLM_EVAL=1 .venv/Scripts/python.exe -m pytest -m llm -q

골든 입력: tests/fixtures/summarize_golden.jsonl (실제 수집분 10건, 학습 5 + 뉴스 5,
광고 섞인 학습 3건 포함 → 필터가 판촉을 지우는지 검증). 출력 스냅샷은
tests/snapshots/summarize/에 저장 → 프롬프트 수정 전후 git diff로 리뷰한다.
"""
import json
import os
import re

import pytest

from collector.models import Item

pytestmark = [
    pytest.mark.llm,
    pytest.mark.skipif(os.environ.get("RUN_LLM_EVAL") != "1",
                       reason="실 API eval — RUN_LLM_EVAL=1일 때만 (쿼터 소비)"),
]

_FIX = os.path.join(os.path.dirname(__file__), "fixtures", "summarize_golden.jsonl")
_SNAP = os.path.join(os.path.dirname(__file__), "snapshots", "summarize")
_CATS = ["AI 모델·기술", "AI 비즈니스·투자", "AI 활용·도구", "한국 AI·스타트업",
         "인프라·에너지", "인재·일의 미래", "개발·학습", "기타"]
_AD = re.compile(r"쿠폰|할인|수강\s*신청|구독|협찬")


def _golden():
    with open(_FIX, encoding="utf-8") as f:
        return [Item(**json.loads(line)) for line in f if line.strip()]


def _snap(item, note):
    os.makedirs(_SNAP, exist_ok=True)
    safe = re.sub(r'[\\/:*?"<>|]', "_", item.title)[:50]
    with open(os.path.join(_SNAP, f"{safe}.md"), "w", encoding="utf-8") as f:
        f.write(f"# {item.title}\n출처: {item.source_name} · learning={item.learning}\n"
                f"카테고리: {note.categories}\n\n{note.summary}\n")


@pytest.mark.parametrize("item", _golden(), ids=lambda it: it.title[:20])
def test_summary_quality(item):
    from collector.summarize import summarize_and_classify
    out = summarize_and_classify(item, categories=_CATS)
    _snap(out, out)

    # 공통: 카테고리 파싱 성공 (빈 값/["기타"] 아닌 유효 분류가 최소 1개)
    assert out.categories, "카테고리 없음"
    assert all(c in _CATS for c in out.categories), f"목록 밖 카테고리: {out.categories}"
    assert "카테고리:" not in out.summary, "카테고리 줄이 요약에 남음"
    # 판촉어 0 (뉴스·학습 공통 — 광고 섞인 골든 입력이 통과 못 하게)
    assert not _AD.search(out.summary), f"판촉성 문구 검출: {item.title[:30]}"

    if item.learning:
        # 학습 카드: 굵은 라벨 구조 + 헤딩 금지 (위키 테마 구조 보호)
        assert "**핵심 개념**" in out.summary, "학습 카드에 핵심 개념 라벨 없음"
        assert "**한 줄 정리**" in out.summary, "학습 카드에 한 줄 정리 없음"
        assert not re.search(r"^#{1,3}\s", out.summary, re.M), "학습 카드에 마크다운 헤딩 존재"
    else:
        # 뉴스 요약: '- ' 불릿 5~7개
        bullets = [ln for ln in out.summary.splitlines() if ln.strip().startswith("- ")]
        assert 4 <= len(bullets) <= 8, f"불릿 개수 이상({len(bullets)}): {item.title[:30]}"
