# 백로그 (나중에 할 것 / 아이디어)

> 1단계에 넣지 않고 미뤄둔 것들. 떠오르면 여기 적고, 때가 되면 요구사항→계획으로 승격.

## 기능 아이디어

- **출처 자동 발굴/추천** — 시스템이 웹·유튜브에서 뜨는 AI 채널/뉴스레터를 검색해 "이거 구독할래?" 추천. (웹검색 + LLM 평가) → Phase 2+ 옵션. *현재는 수동 큐레이션(sources.yaml)만.*
- **푸시 전달** — 텔레그램/이메일로 아침 요약 알림. (1단계는 마크다운 파일 저장만)
- **Q&A (RAG)** — 쌓인 노트에 질문. → Phase 2
- **위키/지식그래프** — understand-anything으로 그래프화. → Phase 3
- **Threads/Twitter(X) 수집** — 어려운 출처. → Phase 4
- **사실검증** — 특정 주장 교차검증(deep-research). 비용 큼, 필요 시 옵션.
- **출처별 수집 개수 제한 / 호출 throttle** — 무료 모델 쿼터 보호. (1단계 첫 실행에서 필요할 수 있음)

## 추가 출처 후보 (원하면 sources.yaml에 추가, 채널ID는 그때 확인)

**유튜브**
- 한국어: 안될과학(Unrealscience), EO(이오), 노마드 코더, 슈카월드(경제·일반)
- 영어: Y Combinator, Lex Fridman, Two Minute Papers, AI Explained, Matthew Berman

**뉴스레터**
- The Batch (Andrew Ng / DeepLearning.AI), Ben's Bites, TLDR AI, Latent Space(swyx), The Rundown AI, Import AI(Jack Clark)
