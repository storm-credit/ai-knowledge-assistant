# 15. 모델 doc 변경 감시기 — 스펙 (v1)

> "AI 지식 비서인데 정작 모델 자체가 뭐 바뀌었는지는 놓친다"는 공백을 메운다.
> Claude·OpenAI·Gemini의 **릴리스노트/changelog**를 매일 확인해, 바뀐 게 있으면
> "무엇이 추가·변경·폐기됐고 우리 시스템에 영향 있나"를 한국어로 정리해 위키에 쌓는다.

- 작성: 2026-07-11 · 전제: Batch 2 완료(쿼터 예산·llm 게이트웨이 가동)

## 확정 결정 (브레인스토밍 4문항)

| # | 결정 |
|---|---|
| 범위 | **릴리스노트·changelog 페이지만** (API 레퍼런스 전체는 노이즈 커서 제외) |
| 감지 | **스냅샷 diff → 변경 있을 때만 LLM 요약** (변경 0이면 LLM 0콜) |
| 출력 | **`notes/model-updates/YYYY-MM-DD.md`** 별도 + 웹 `/models` 탭 |
| 주기 | **매일 cron 끝에 1스텝** (변경 없으면 0콜) |

## 데이터 흐름

```
model_docs.yaml (provider별 감시 URL)
  └─ 각 URL:
       fetch(httpx) → _html_to_text(정규식 HTML strip + 공백 정규화)
       → state/model_docs/<slug>.txt (이전 스냅샷) 과 difflib 비교
       ├─ 스냅샷 없음(첫 실행): baseline만 저장, LLM 0콜
       ├─ 변경 없음: skip (LLM 0콜)
       └─ 변경 있음: diff(추가/변경 줄) → WATCH_PROMPT로 LLM 1콜 요약
                     → 그날 notes/model-updates/YYYY-MM-DD.md에 섹션 추가
                     → 요약 성공 후에만 스냅샷 갱신
```

## 핵심 설계 결정

1. **스냅샷은 요약 성공 후에만 갱신.** 쿼터 소진(QuotaExhausted)·요약 실패 시 옛 스냅샷을
   유지해 다음 실행에 같은 변경분을 다시 시도한다(기존 파이프라인의 retry-later 철학). 변경 놓침 방지.
2. **첫 실행 = baseline만.** 비교 대상이 없으면 요약하지 않는다(잡음·낭비 방지).
3. **환각 차단.** LLM에는 diff의 변경 줄만 주고 "diff에 없는 내용은 지어내지 마라, 광고·판촉 무시".
   출력은 개발자 관점 불릿 + '우리 영향' 표시. 원문 근거 없는 추측 금지.
4. **JS 전용 페이지 방어.** fetch 결과 텍스트가 비정상적으로 짧으면(예: <200자) skip + 경고.
   (SPA로만 렌더되는 docs는 v1 범위 밖 → BACKLOG.)
5. **URL별 실패 격리.** 한 URL fetch 실패가 나머지를 막지 않는다(개별 try/except).

## 구성요소 (isolation)

| 부품 | 무엇을 / 의존 |
|---|---|
| `model_docs.yaml` | provider별 감시 URL 목록. 추가/삭제는 여기 한 곳(= sources.yaml 패턴). |
| `collector/watch.py` | 순수 로직 + I/O 글루. `fetch` 주입 가능(테스트). `_html_to_text`, `diff_text`, `summarize_change`, `run_watch`. LLM은 `collector/llm.py` 경유(예산 적용). |
| `state/model_docs/*.txt` | URL별 이전 스냅샷 (gitignore — 런타임 상태). |
| `notes/model-updates/*.md` | 날짜별 변경 기록. `# YYYY-MM-DD 모델 업데이트` + provider별 `## ` 섹션. |
| `collector/__main__.py` | `run` 끝에 `run_watch()` 추가 + 독립 `watch-docs` 서브커맨드. 실행 락 안에서. |
| `web/render.py`·`app.py` | `list_model_updates`·`load_model_update` + `/models`, `/models/<date>` 라우트 + nav 탭. |

## WATCH_PROMPT (개요)

```
다음은 {provider} 모델 문서의 변경 diff다(+ 추가, - 삭제 줄).
개발자 관점에서 무엇이 추가·변경·폐기됐는지 한국어 불릿으로 정리하라.
- 새 모델/기능/파라미터/가격/폐기(deprecation)를 우선.
- 우리 시스템(Gemini API·flash-lite 사용)에 영향이 있으면 각 항목 끝에 '(영향)' 표시.
- diff에 없는 내용은 지어내지 마라. 광고·마케팅 문구는 무시.
- 마크다운 헤딩('#') 쓰지 말고 '- ' 불릿만.

diff:
{diff}
```

## model_docs.yaml (초안 — 구현 시 URL 검증)

```yaml
# 모델 문서 감시 대상. 추가/삭제는 여기 한 곳.
providers:
  - name: Claude
    url: https://docs.anthropic.com/en/release-notes/api
  - name: OpenAI
    url: https://platform.openai.com/docs/changelog
  - name: Gemini
    url: https://ai.google.dev/gemini-api/docs/changelog
```
(구현 단계에서 각 URL이 정적 HTML로 텍스트를 주는지 fetch 검증 — SPA면 대체 URL 탐색/BACKLOG.)

## 테스트 (TDD)

- `_html_to_text`: 태그 제거·공백 정규화·script/style 제거
- `diff_text`: 변경 없음→빈, 추가/삭제 줄 추출, 첫 실행(baseline) 처리
- `run_watch`: fetch 주입 — 첫 실행 baseline 0콜, 변경 시 1콜+노트 작성+스냅샷 갱신, 변경 없음 0콜, 요약 실패 시 스냅샷 미갱신(재시도), URL 실패 격리
- 웹: `/models` 목록·상세, 없는 날짜 404
- (선택) `-m llm` eval: 합성 diff 하나로 요약 품질 스냅샷

## 스코프 밖 (YAGNI)

바뀐 기능 실제 API 검증, SPA 렌더링(headless), 페이지 구조 변경 자동 무시, 알림 푸시(백로그와 묶음).
