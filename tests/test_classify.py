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

def test_classify_validates_against_known_topics():
    # known_topics가 주어지면 그게 모델에 보여지고, 그 값으로 검증돼야 한다 (기타로 붕괴 금지)
    out = classify_item(_item(), known_topics=["커스텀주제"],
                        client=FakeClient("커스텀주제"))
    assert out == ["커스텀주제"]


def test_classify_max_two_valid():
    out = classify_item(_item(), known_topics=[],
                        client=FakeClient("AI 모델·기술, AI 비즈니스·투자, AI 활용·도구"))
    assert out == ["AI 모델·기술", "AI 비즈니스·투자"]   # 최대 2개
