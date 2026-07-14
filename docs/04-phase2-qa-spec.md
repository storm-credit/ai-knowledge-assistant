# 04. 2단계 요구사항 정의서 — Q&A 웹 화면  🔄 구현 중 (2026-07-14 착수)

> **상태: 구현 중.** 원안(2026-06-27, 아래 §1~6)은 그대로 유효하되, 그동안 아키텍처가
> 발전(web/ Flask 앱, collector/llm.py 게이트웨이+예산, render.search_notes)해서
> **아래 §7 "현대화 구현 계약"대로** 기존 앱에 얹는다.

## 7. 현대화 구현 계약 (2026-07-14)

- **위치:** 별도 collector/web.py 대신 **기존 web/app.py에 `/ask` 라우트** 추가. 순수 로직은 `collector/qa.py`.
- **LLM:** `collector/llm.py`의 `complete_text`(예산·서킷브레이커·키로테이션·503 재시도 내장) 사용. 질문당 1콜, 예산 부족 시 안내.
- **검색:** 키워드(벡터DB 없음). topics+daily+learn 노트 스캔. `render.search_notes` 패턴 재사용/차용.

### 인터페이스 (양 계층이 맞출 계약)
```python
# collector/qa.py
QA_PROMPT: str   # 근거에만 기반·출처 인용·없으면 "근거 없음" 정직하게·지어내기 금지
@dataclass
class QAChunk: kind: str; name: str; title: str; href: str; text: str
def retrieve(question, *, topics_dir, daily_dir, learn_dir, limit=8) -> list[QAChunk]  # LLM 0콜
def answer(question, *, client=None, clients=None, budget=None, model="gemini-2.5-flash-lite") -> dict
    # 반환: {"answer": str, "sources": [{"title","href","kind"}], "grounded": bool}
    # 청크 0개 → {"answer":"관련 근거를 찾지 못했습니다.", "sources":[], "grounded":False} (LLM 0콜)
    # 예산 소진(QuotaExhausted) → 그대로 전파(라우트가 안내 문구로 처리)
```

### 웹 `/ask`
- GET `/ask` : 질문 입력창(+선택: 기간). nav에 "질문" 탭.
- POST(or GET `?q=`) : `qa.answer(q)` → 답변 + 출처 링크 목록 렌더. 오토이스케이프(XSS 안전).

### 성공 기준 (eval)
- 관련 질문 → 근거 기반 한국어 답변 + 출처 링크 ≥1. 무관 질문 → "근거 없음" 정직.
- `pytest -m llm` 골든 1~2건(예: "이번주 메모리 시장 동향?" → 근거·출처 존재).

### 스코프 밖 (YAGNI)
벡터DB 의미검색, 대화 히스토리·멀티턴, 공개 배포, 멀티유저.

## 1. 목적 & 범위

- **목적:** 브라우저에서 질문하면, 쌓인 노트(`notes/daily/*.md`)를 근거로 **AI가 한국어로 답하고 출처를 보여준다.**
- **범위(포함):** 로컬 웹 페이지, 질문 입력 + 기간(지난 N일) 선택, 노트 검색(날짜+키워드), Gemini 답변, 출처 링크 표시.
- **범위(제외, 나중):** 벡터DB 의미검색, 로그인/멀티유저, 공개 배포. → 백로그.

## 2. 기능 요구사항 (FR)

| ID | 요구사항 |
|---|---|
| FR-1 | 로컬 웹 페이지를 제공한다 (`python -m collector web` → 브라우저 오픈, 예: localhost:8765) |
| FR-2 | 질문 입력창 + "지난 N일"(기본 7) 선택 UI |
| FR-3 | 질문 시, 기간 내 노트에서 (키워드 포함) **관련 요약을 추린다** |
| FR-4 | 추린 요약 + 질문을 Gemini에 보내 **한국어 답변**을 생성한다 |
| FR-5 | 답변과 함께 **근거가 된 원본 링크 목록**을 표시한다 (검증/추적) |
| FR-6 | Gemini 호출은 **기존 3키 로테이션**을 재사용한다 (429 시 다음 키) |

## 3. 확정된 결정

- **검색 방식:** 날짜+키워드 필터 → LLM (방안 A). **벡터DB 없음** (현재 규모엔 불필요; 수천 건 넘으면 백로그의 벡터DB 추가).
- **모델:** `gemini-2.5-flash-lite` (1단계와 동일, 무료).
- **웹 프레임워크:** Flask (가벼움, 의존성 1개 추가).
- **포트:** 8765 (로컬 전용, 127.0.0.1).

## 4. 아키텍처

```
[브라우저] 127.0.0.1:8765
  질문 + 지난 N일 → 답변 + 출처 링크
        ↓ (POST /ask)
[Flask 앱]  collector/web.py
   1. retrieve.search(question, days) → 관련 Item/요약 목록
   2. Gemini(flash-lite, 3키 로테이션)에 "질문 + 추린 요약" 전달
   3. {answer, sources[]} 반환
        ↓
[검색]  collector/retrieve.py  — notes/daily/*.md 파싱 → 날짜·키워드 필터
```
- **새 파일:** `collector/retrieve.py`(노트 검색·필터), `collector/web.py`(Flask 앱 + HTML).
- **재사용:** `summarize._default_clients()`(키 로테이션), 마크다운 파싱.

## 5. 비기능 요구사항
- **비용:** 무료(기존 키 재사용). **로컬 전용**(127.0.0.1).
- **신뢰성:** 답변은 추린 노트에 **근거**하고 출처를 표기(환각 최소화, 원문 없는 내용 지어내지 않기).
- **안정성:** 노트 없거나 검색 0건이면 "관련 내용 없음"을 안내.

## 6. 성공 기준
- 브라우저에서 "이번주 SaaS 트렌드 정리해줘" 입력 → 지난 7일 노트 기반 **한국어 요약 답변 + 출처 링크 3~N개**가 표시된다.
- 관련 없는 질문엔 "근거 없음"을 정직하게 답한다.
- 한도 초과 시 키 로테이션으로 자동 처리.
