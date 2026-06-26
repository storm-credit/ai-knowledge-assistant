# 개인 AI 지식 비서 — 프로젝트 개요 & 진행 보드

> 이 문서는 프로젝트의 **목차이자 진행 상황판**입니다. PM처럼 단계별로 문서를 남기고, 지금 어디까지 왔는지 한눈에 봅니다.

- **프로젝트명:** 개인 AI 지식 비서 (Personal AI Knowledge Assistant)
- **한 줄 정의:** AI 관련 정보를 매일 자동 수집·요약·저장하고, 아침 요약·Q&A·위키로 활용하는 나만의 지식 시스템
- **엔진:** Hermes Agent (로컬 Docker)
- **작성 시작:** 2026-06-26
- **현재 단계:** 구현 계획(3단계) ✅ 작성됨 → 구현(4단계) 실행 대기
- **GitHub:** https://github.com/storm-credit/ai-knowledge-assistant

> 📘 **[`PLAYBOOK.md`](PLAYBOOK.md)** — 이 진행 방식을 일반화한 **재사용 템플릿**. 다음 프로젝트 때 이걸 복사해서 쓰면 됨.

## PM 단계 ↔ 문서 매핑 (진행 보드)

| # | PM 단계 | 산출 문서 | 상태 |
|---|---|---|---|
| 1 | 컨셉 / 아키텍처 | [`01-concept-and-architecture.md`](01-concept-and-architecture.md) | ✅ 확정 |
| 2 | 요구사항 정의서 | [`02-requirements-spec.md`](02-requirements-spec.md) | ✅ 확정 (결정 5개 완료) |
| 3 | 구현 계획 (구성요소표·작업분해) | [`03-implementation-plan.md`](03-implementation-plan.md) | ✅ 작성됨 (11개 태스크, TDD) |
| 4 | 구현 / 개발 | (collector 패키지 + 스케줄) | ⏳ 실행 대기 |

## 핵심 원칙 (왜 이렇게 가나)

1. **한 번에 다 만들지 않는다.** 가장 작은 쓸모 있는 1단계부터 굴리고 얹는다.
2. **출처는 자유롭게 늘리고 줄인다.** 시스템이 출처 변화에 유연해야 한다.
3. **쉬운 출처부터.** 유튜브·뉴스레터(쉬움) → 웹(보통) → Threads/X(어려움, 마지막).
4. **단계마다 문서를 남긴다.** (지금 이거)
