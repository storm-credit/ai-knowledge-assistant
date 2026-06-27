from collector.wikisynth import synthesize_overview

class FakeResp:
    def __init__(self,c): self.choices=[type("C",(),{"message":type("M",(),{"content":c})})]
class FakeClient:
    def __init__(self,c): self._c=c; self.chat=type("Ch",(),{"completions":self})()
    def create(self,**k): return FakeResp(self._c)

def test_synthesize_parses_overview_and_related():
    items = [{"title":"글a","summary":"요약a"},{"title":"글b","summary":"요약b"}]
    fake = FakeClient("개요: 이것은 정리된 개요다.\n관련주제: Claude, SaaS")
    ov, rel = synthesize_overview("AI 에이전트", items, client=fake)
    assert "정리된 개요" in ov
    assert rel == ["Claude", "SaaS"]
