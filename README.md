# 개인 AI 지식 비서 (Personal AI Knowledge Assistant)

AI 관련 정보(유튜브·뉴스레터 등)를 매일 자동 수집 → AI 요약 → 저장하고,
아침 요약·Q&A·위키로 활용하는 나만의 지식 시스템. 엔진은 [Hermes Agent](https://github.com/NousResearch/hermes-agent).

## 폴더 구조

```
ai-knowledge-assistant/
├─ docs/        PM 문서 (기획→요구사항→구현계획) + PLAYBOOK(재사용 템플릿)
└─ notes/       수집·요약된 지식이 쌓이는 곳 (Obsidian 볼트)
   └─ daily/    날짜별 요약 노트
```

## 사용법

- **PM 문서:** `docs/00-overview.md`(진행 보드)부터 보기.
- **Obsidian:** 이 폴더(`ai-knowledge-assistant`)를 Obsidian 볼트로 열면 `notes/`의 지식 그래프를 탐색 가능.
- **웹 뷰어(다크 UI):** `python -m web.app` 실행 후 http://127.0.0.1:5000 접속.
  주제별 정리형 위키 + 날짜별 데일리 요약을 브라우저에서 열람. (Flask, 로컬 전용)

## 진행 상태

기획 단계 — 요구사항 정의 중. 자세한 건 [`docs/00-overview.md`](docs/00-overview.md).
