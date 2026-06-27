from collector.models import Item
from collector.classify import classify_item

class FakeResp:
    def __init__(self, c): self.choices=[type("C",(),{"message":type("M",(),{"content":c})})]
class FakeClient:
    def __init__(self, c): self._c=c; self.chat=type("Ch",(),{"completions":self})()
    def create(self, **k): return FakeResp(self._c)

def test_classify_returns_topics_max3():
    it = Item(source_name="조코딩", source_type="youtube", id="x",
              title="AI 에이전트 시대", link="l", published="", summary="에이전트 요약")
    out = classify_item(it, known_topics=["Claude"],
                        client=FakeClient("AI 에이전트, Claude, 바이브코딩, 여분"))
    assert out == ["AI 에이전트", "Claude", "바이브코딩"]  # 최대 3개, # 제거
