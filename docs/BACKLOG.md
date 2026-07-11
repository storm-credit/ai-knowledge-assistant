# 백로그 (나중에 할 것 / 아이디어)

> 1단계에 넣지 않고 미뤄둔 것들. 떠오르면 여기 적고, 때가 되면 요구사항→계획으로 승격.

## 기능 아이디어

- **모델 doc 감시기 — Claude 소스 추가** — Claude 릴리스노트(docs.anthropic.com/en/release-notes/api)는 본문이 JS로 렌더(SPA)라 정적 fetch로 못 가져옴(2026-07-11 확인). headless 렌더(playwright 등) 또는 정적 대체 소스 확보 시 model_docs.yaml에 추가. (현재 Gemini·OpenAI만 감시.)


- **학습 노트 웹 근거 보강** — 니치 신조어(예: "하네스 엔지니어링")는 피드 원문에 정의가 없고 flash-lite 일반지식도 약해 오해석함(07-03 eval 실전 발견 — (불확실) 마커는 작동). 웹 검색으로 정의 근거를 가져와 '이게 뭔가' 섹션에 주입하는 옵션 검토. 쿼터/비용 추가라 보류.

- **모델 doc 변경 감시기** ⭐ — Claude·OpenAI(Codex)·Gemini의 **공식 docs/changelog**를 주기적으로 fetch → 이전 스냅샷과 **diff** → "무엇이 추가·변경·폐기됐나 + 우리 시스템에 영향?" 검증 → 위키 `모델 업데이트` 페이지. RSS 없는 경우가 많아 fetch+스냅샷 diff 방식(기존 피드 수집과 별개 부품). 바뀐 기능을 실제로 찔러 검증(eval 트랙 연결). *AI 지식 비서인데 정작 모델 자체 변화는 놓치는 공백을 메움.*

- **출처 자동 발굴/추천** — 시스템이 웹·유튜브에서 뜨는 AI 채널/뉴스레터를 검색해 "이거 구독할래?" 추천. (웹검색 + LLM 평가) → Phase 2+ 옵션. *현재는 수동 큐레이션(sources.yaml)만.*
- **푸시 전달** — 텔레그램/이메일로 아침 요약 알림. (1단계는 마크다운 파일 저장만)
- **Q&A (RAG) 웹 화면** — 쌓인 노트에 질문. ⏸️ **설계 완료·보류** (스펙: `04-phase2-qa-spec.md`). 필요해지면 그대로 구현.
- **옵시디언 볼트 → 웹 위키 공개** — 마크다운 노트를 정적 웹사이트로 (Quartz/MkDocs 무료, Obsidian Publish 유료, 또는 직접 제작). 독립 작업, 나중에.
- **위키/지식그래프** — understand-anything으로 그래프화. → Phase 3
- **Threads/Twitter(X) 수집** — 어려운 출처. → Phase 4
- **사실검증** — 특정 주장 교차검증(deep-research). 비용 큼, 필요 시 옵션.
- **출처별 수집 개수 제한 / 호출 throttle** — 무료 모델 쿼터 보호. (1단계 첫 실행에서 필요할 수 있음)

## 추가 출처 후보 (원하면 sources.yaml에 추가, 채널ID는 그때 확인)

**유튜브**
- 한국어: 안될과학(Unrealscience), EO(이오), 노마드 코더, 슈카월드(경제·일반)
- 영어: Y Combinator, Lex Fridman, Two Minute Papers, AI Explained, Matthew Berman

**뉴스레터**
- The Batch (Andrew Ng / DeepLearning.AI) — ⚠️ 공식 RSS 없음. RSSHub(`/deeplearning/thebatch`) 경유만 가능하나 공개 인스턴스 403. 자체 호스팅 시 학습형으로 추가 검토.
- TLDR AI(`https://tldr.tech/api/rss/ai`, 검증됨, 뉴스형) — 학습형 아님. 일반 뉴스로 추가할지 검토.
- Ben's Bites, Latent Space(swyx), The Rundown AI, Import AI(Jack Clark)
