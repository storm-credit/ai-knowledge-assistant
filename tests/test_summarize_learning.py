"""학습형 항목은 LEARNING_PROMPT로 학습 카드를 만든다."""
from collector.models import Item
from collector.summarize import summarize_and_classify


class RecResp:
    def __init__(self, c):
        self.choices = [type("C", (), {"message": type("M", (), {"content": c})})]


class RecClient:
    """create()에 넘어온 프롬프트를 기록하는 페이크 클라이언트."""
    def __init__(self, c):
        self._c = c
        self.seen = None
        self.chat = type("Ch", (), {"completions": self})()

    def create(self, **k):
        self.seen = k["messages"][0]["content"]
        return RecResp(self._c)


def _item(learning):
    return Item(source_name="노마드코더", source_type="youtube", id="x",
                title="파이썬 기초", link="l", published="", raw_text="원문",
                learning=learning)


CATS = ["개발·학습", "AI 모델·기술", "기타"]


def test_learning_item_uses_learning_prompt():
    fake = RecClient("**핵심 개념**\n- a\n\n**한 줄 정리**\n요약\n카테고리: 개발·학습")
    summarize_and_classify(_item(True), client=fake, categories=CATS)
    assert "학습 카드" in fake.seen
    assert "핵심 개념" in fake.seen
    assert "헤딩" in fake.seen  # 헤딩 금지 지시가 프롬프트에 있어야


def test_learning_prompt_excludes_promotional_content():
    # 광고·쿠폰·수강권유 등 판촉성 내용 제외 지시가 프롬프트에 있어야
    fake = RecClient("**핵심 개념**\n- a\n카테고리: 개발·학습")
    summarize_and_classify(_item(True), client=fake, categories=CATS)
    assert "쿠폰" in fake.seen
    assert "제외" in fake.seen


def test_non_learning_item_uses_news_prompt():
    fake = RecClient("- 포인트\n카테고리: AI 모델·기술")
    summarize_and_classify(_item(False), client=fake, categories=CATS)
    assert "학습 카드" not in fake.seen
    assert "핵심 포인트" in fake.seen  # 기존 뉴스 요약 프롬프트


def test_learning_card_body_preserved_without_category_line():
    fake = RecClient("**핵심 개념**\n- 변수와 타입\n\n```python\nx = 1\n```\n"
                     "**한 줄 정리**\n기초를 다진다\n카테고리: 개발·학습")
    out = summarize_and_classify(_item(True), client=fake, categories=CATS)
    assert "**핵심 개념**" in out.summary
    assert "```python" in out.summary
    assert "카테고리" not in out.summary
    assert "## " not in out.summary  # 헤딩 없음 → 위키 구조와 충돌 안 함
    assert out.categories == ["개발·학습"]


def test_learning_defaults_to_dev_category_when_none_found():
    fake = RecClient("**핵심 개념**\n- a\n**한 줄 정리**\n요약")  # 카테고리 줄 없음
    out = summarize_and_classify(_item(True), client=fake, categories=CATS)
    assert out.categories == ["개발·학습"]
