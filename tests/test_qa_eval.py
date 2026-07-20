"""Q&A 품질 eval (docs/04 성공기준) — 실 API. RUN_LLM_EVAL=1일 때만.

    RUN_LLM_EVAL=1 .venv/Scripts/python.exe -m pytest -m llm -q

실제 쌓인 노트(notes/)에 질문해 근거·출처가 나오는지 확인. 스냅샷 저장.
"""
import os
import re

import pytest

pytestmark = [
    pytest.mark.llm,
    pytest.mark.skipif(os.environ.get("RUN_LLM_EVAL") != "1",
                       reason="실 API eval — RUN_LLM_EVAL=1일 때만 (쿼터 소비)"),
]

SNAP = os.path.join(os.path.dirname(__file__), "snapshots", "qa")


@pytest.mark.parametrize("question", [
    "최근 메모리 시장 동향 정리해줘",
    "AI 에이전트 관련해서 나온 얘기 있어?",
])
def test_qa_grounded_answer(question):
    from collector import qa
    out = qa.answer(question)
    os.makedirs(SNAP, exist_ok=True)
    safe = re.sub(r'[\\/:*?"<>|]', "_", question)[:40]
    with open(os.path.join(SNAP, f"{safe}.md"), "w", encoding="utf-8") as f:
        f.write(f"# {question}\n\ngrounded={out['grounded']}\n\n{out['answer']}\n\n"
                f"## 출처\n" + "\n".join(f"- {s['kind']}: {s['title']}" for s in out["sources"]))
    assert out["grounded"] is True, "근거를 못 찾음 (노트가 쌓였는지 확인)"
    assert out["sources"], "출처가 비어 있음"
    assert out["answer"] and "관련 근거를 찾지 못했습니다" not in out["answer"]
