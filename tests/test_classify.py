from collector.models import Item
from collector.classify import classify_item, CATEGORIES

class FakeResp:
    def __init__(self, c): self.choices=[type("C",(),{"message":type("M",(),{"content":c})})]
class FakeClient:
    def __init__(self, c): self._c=c; self.chat=type("Ch",(),{"completions":self})()
    def create(self, **k): return FakeResp(self._c)

def _item():
    return Item(source_name="조코딩", source_type="youtube", id="x",
                title="AI 에이전트 시대", link="l", published="", summary="에이전트 요약")

def test_categories_constant():
    assert CATEGORIES == ["AI 모델·기술", "AI 비즈니스·투자", "AI 활용·도구",
                          "한국 AI·스타트업", "인프라·에너지", "인재·일의 미래", "기타"]

def test_classify_filters_to_valid_categories():
    out = classify_item(_item(), known_topics=[],
                        client=FakeClient("AI 모델·기술, 엉뚱한것"))
    assert out == ["AI 모델·기술"]   # 유효하지 않은 카테고리는 제거

def test_classify_all_invalid_returns_etc():
    out = classify_item(_item(), known_topics=[],
                        client=FakeClient("엉뚱한것, 또다른엉뚱"))
    assert out == ["기타"]

def test_classify_always_allows_base_categories(self_unused=None):
    # v2.1: 검증 대상은 항상 categories.yaml(고정 목록). known_topics가 제한하지 않는다 (Fix 4)
    out = classify_item(_item(), known_topics=["AI 모델·기술"],
                        client=FakeClient("AI 비즈니스·투자"))
    assert out == ["AI 비즈니스·투자"]   # known_topics에 없는 기본 카테고리도 도달 가능


def test_classify_no_clients_raises_runtimeerror():
    # 키/클라이언트가 비면 RuntimeError (TypeError 아님) (Fix 6)
    import pytest
    with pytest.raises(RuntimeError):
        classify_item(_item(), known_topics=[], clients=[])


def test_classify_handles_none_body():
    # summary 빈 문자열, raw_text None 이어도 TypeError 없이 분류 (Fix 7)
    item = Item(source_name="s", source_type="youtube", id="x",
                title="AI 모델 발표", link="l", published="", summary="", raw_text=None)
    out = classify_item(item, known_topics=[], client=FakeClient("AI 모델·기술"))
    assert out == ["AI 모델·기술"]


def test_classify_max_two_valid():
    out = classify_item(_item(), known_topics=[],
                        client=FakeClient("AI 모델·기술, AI 비즈니스·투자, AI 활용·도구"))
    assert out == ["AI 모델·기술", "AI 비즈니스·투자"]   # 최대 2개
