"""적용형 학습 노트 — 실 API 품질 eval (docs/14 결정 4).

PLAYBOOK 7절 'AI 전문가 트랙'의 첫 적용: 프롬프트를 수정하면 이걸 수동 1회 돌려
품질 회귀를 잡는다. cron·평시 pytest에서는 실행되지 않는다 (환경변수 게이트).

    RUN_LLM_EVAL=1 .venv/Scripts/python.exe -m pytest -m llm -q

출력 스냅샷은 tests/snapshots/learn/에 저장 → 수정 전후 git diff로 리뷰.
"""
import os
import re

import pytest

pytestmark = [
    pytest.mark.llm,
    pytest.mark.skipif(os.environ.get("RUN_LLM_EVAL") != "1",
                       reason="실 API eval — RUN_LLM_EVAL=1일 때만 (쿼터 소비)"),
]

# 골든 개념 2건 (고정 — 바꾸면 스냅샷 diff의 의미가 사라짐)
GOLDEN = ["프롬프트 엔지니어링", "MCP"]
# eval용 고정 프로필 (사용자 me.md와 분리해 재현성 확보)
PROFILE = "파이썬과 Claude Code로 개인 자동화 도구를 만든다. PM 방식(스펙→위임→검증)으로 일하는 걸 선호."
TOPICS = ["AI 모델·기술", "AI 활용·도구", "개발·학습"]
SNAP_DIR = os.path.join(os.path.dirname(__file__), "snapshots", "learn")


@pytest.mark.parametrize("concept", GOLDEN)
def test_learn_note_quality(concept):
    from collector.learn import build_prompt, compose_note
    from collector.llm import complete_text

    prompt = build_prompt(concept, profile=PROFILE, context=[], topics=TOPICS)
    body = complete_text([{"role": "user", "content": prompt}])
    note = compose_note(concept, body, date="eval")

    os.makedirs(SNAP_DIR, exist_ok=True)
    with open(os.path.join(SNAP_DIR, f"{concept}.md"), "w", encoding="utf-8") as f:
        f.write(note)

    # 체크리스트 (docs/14): 4섹션 존재
    for sec in ("## 이게 뭔가", "## 어떻게 배우나", "## 내 적용법", "## 관련"):
        assert sec in note, f"섹션 누락: {sec}"
    # 내 적용법은 추론 → 추측 표시 필수
    assert "(제안)" in note, "'내 적용법'에 (제안) 표시 없음"
    # 판촉어 0
    assert not re.search(r"쿠폰|할인|수강\s*신청|구독", note), "판촉성 문구 검출"
    # 프로필 반영 (고정 프로필의 키워드 중 하나는 적용법에 나타나야)
    apply_sec = note.split("## 내 적용법", 1)[1].split("##", 1)[0]
    assert re.search(r"파이썬|Claude|자동화|PM", apply_sec), "적용법에 프로필 반영 안 됨"
