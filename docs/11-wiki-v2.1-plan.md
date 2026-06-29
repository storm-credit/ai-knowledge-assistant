# 위키 v2.1 (운영 관리) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** (1) 카테고리를 `categories.yaml` 파일로 편집 가능하게, (2) 토픽 페이지의 `## ✍️ 내 메모` 구역을 자동 재생성에도 보존. (쿼터 불필요 — 순수 코드)

**Architecture:** classify가 카테고리를 파일에서 로드(없으면 기본 상수). render_page가 마커로 둘러싼 메모 구역을 출력하고, write_pages가 기존 파일의 메모를 읽어 새 페이지에 그대로 끼워넣는다. (아카이브는 데이터 적어 보류)

**Tech Stack:** 기존 Python collector, PyYAML(이미 사용), pytest. LLM 호출 없음.

---

## Task 1: categories.yaml 로더

**Files:** Modify `collector/classify.py`, Create `categories.yaml`, Test `tests/test_categories_config.py`

- [ ] **Step 1: 실패 테스트**
```python
def test_load_categories_from_file_and_default(tmp_path, monkeypatch):
    from collector import classify
    # 파일 있으면 그걸 사용
    p = tmp_path / "categories.yaml"
    p.write_text("categories:\n  - 가\n  - 나\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert classify.load_categories() == ["가", "나"]
    # 파일 없으면 기본 상수
    (tmp_path / "categories.yaml").unlink()
    assert classify.load_categories() == classify.CATEGORIES
```

- [ ] **Step 2: 실패 확인** — `.venv/Scripts/python -m pytest tests/test_categories_config.py -v` → FAIL (load_categories 없음)

- [ ] **Step 3: 구현** — `collector/classify.py` 수정:
  1. 상단에 추가: `import os, yaml`  (기존 import 유지)
  2. `CATEGORIES = [...]` 정의 바로 아래에 추가:
```python
def load_categories(path: str = "categories.yaml") -> list:
    """categories.yaml이 있으면 거기서, 없으면 기본 CATEGORIES."""
    try:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            cats = [str(c).strip() for c in (data.get("categories") or []) if str(c).strip()]
            if cats:
                return cats
    except Exception:
        pass
    return CATEGORIES
```
  3. `classify_item` 안에서 `CATEGORIES`를 `load_categories()`로 교체:
     - `categories = known_topics or load_categories()`
     - `cats = load_categories()` 를 함수 앞에서 한 번 구해 `valid = [p for p in parts if p in cats][:2]`

- [ ] **Step 4: 기본 categories.yaml 생성**
`categories.yaml`:
```yaml
# 위키 카테고리. 추가/이름변경은 여기서 (적용은 다음 분류 실행 때).
categories:
  - AI 모델·기술
  - AI 비즈니스·투자
  - AI 활용·도구
  - 한국 AI·스타트업
  - 인프라·에너지
  - 인재·일의 미래
  - 기타
```

- [ ] **Step 5: 통과 + 커밋** — `pytest -q` PASS → `git add collector/classify.py categories.yaml tests/test_categories_config.py && git commit -m "feat(wiki): categories.yaml editable category list"`

---

## Task 2: ✍️ 내 메모 보존

**Files:** Modify `collector/topics.py`, Test `tests/test_topics_memo.py`

- [ ] **Step 1: 실패 테스트**
```python
import os
from collector.models import Item
from collector.topics import TopicStore, write_pages, MEMO_START, MEMO_END

def test_memo_preserved_across_regen(tmp_path):
    out = tmp_path / "topics"
    s = TopicStore(str(tmp_path / "t.json"))
    s.add_item("AI", Item(source_name="s", source_type="x", id="a", title="T",
               link="http://a", published="2026-06-29", summary="요약"))
    write_pages(s, str(out))
    p = out / "AI.md"
    txt = p.read_text(encoding="utf-8")
    assert MEMO_START in txt and MEMO_END in txt            # 메모 구역 존재
    # 사용자가 메모 작성
    edited = txt.replace(txt[txt.find(MEMO_START)+len(MEMO_START):txt.find(MEMO_END)],
                         "\n내가 적은 메모\n")
    p.write_text(edited, encoding="utf-8")
    # 재생성
    write_pages(s, str(out))
    txt2 = p.read_text(encoding="utf-8")
    assert "내가 적은 메모" in txt2                          # 보존됨
```

- [ ] **Step 2: 실패 확인** — `pytest tests/test_topics_memo.py -v` → FAIL (MEMO_START 없음 / 보존 안 됨)

- [ ] **Step 3: 구현** — `collector/topics.py`:
  1. 상단(`import re as _re` 근처)에 상수 추가:
```python
MEMO_START = "<!-- memo:start -->"
MEMO_END = "<!-- memo:end -->"
DEFAULT_MEMO = "여기에 메모·정정을 적으세요. 자동 갱신해도 보존됩니다."

def _extract_memo(text: str):
    i = text.find(MEMO_START); j = text.find(MEMO_END)
    if i != -1 and j != -1 and j > i:
        return text[i + len(MEMO_START):j].strip()
    return None

def _replace_memo(text: str, memo: str) -> str:
    i = text.find(MEMO_START); j = text.find(MEMO_END)
    if i != -1 and j != -1 and j > i:
        return text[:i + len(MEMO_START)] + "\n" + memo + "\n" + text[j:]
    return text
```
  2. `render_page`에서 `if t.get("related"):` 블록 **앞에** 메모 섹션 추가:
```python
    lines += ["## ✍️ 내 메모", MEMO_START, DEFAULT_MEMO, MEMO_END, ""]
```
  3. `write_pages`의 파일 쓰기 부분을 교체 — 기존:
```python
        with open(p, "w", encoding="utf-8") as f:
            f.write(render_page(topic, t))
```
     →
```python
        content = render_page(topic, t)
        if os.path.exists(p):
            old_memo = _extract_memo(open(p, encoding="utf-8").read())
            if old_memo and old_memo != DEFAULT_MEMO:
                content = _replace_memo(content, old_memo)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
```

- [ ] **Step 4: 통과 확인** — `pytest tests/test_topics_memo.py -v` → PASS; 전체 `pytest -q` PASS (다른 렌더 테스트가 메모 섹션 추가로 깨지지 않는지; 깨지면 단정문 보완)
- [ ] **Step 5: 커밋** — `git add collector/topics.py tests/test_topics_memo.py && git commit -m "feat(wiki): preserve ## 내 메모 region across regeneration"`

---

## Task 3: 검증 + 병합 (재렌더는 내일 자동 실행에 위임)

- [ ] **Step 1: 전체 테스트** — `.venv/Scripts/python -m pytest -q` → 모두 PASS
- [ ] **Step 2: 병합 + 푸시**
```bash
git checkout master && git merge --no-ff <branch> -m "Merge wiki v2.1: categories.yaml + memo preservation"
git push origin master
```
- [ ] **Step 3: (재렌더 안 함)** — 현재 topics.json은 어제 실패한 빈 상태라 지금 재렌더하면 빈 페이지가 됨. 메모 구역·categories.yaml은 **내일 새벽 자동 실행(정리형 재생성)** 때 함께 적용된다.

---

## 완료 정의
- `categories.yaml` 수정으로 카테고리 목록 변경 가능(다음 분류 실행에 반영).
- 토픽 페이지에 `## ✍️ 내 메모` 구역이 있고, 거기 적은 내용은 자동 재생성 후에도 **보존**된다.
- LLM 호출 0 (쿼터 무관).
