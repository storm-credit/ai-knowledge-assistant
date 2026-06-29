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


def test_synthesize_structure_parses_themes_orphans():
    from collector.wikisynth import synthesize_structure
    class R:
        def __init__(s,c): s.choices=[type("C",(),{"message":type("M",(),{"content":c})})]
    class FC:
        def __init__(s,c): s._c=c; s.chat=type("Ch",(),{"completions":s})()
        def create(s,**k): return R(s._c)
    items = [{"title":"A","summary":"a"},{"title":"B","summary":"b"},
             {"title":"C","summary":"c"},{"title":"D","summary":"d"}]
    out = synthesize_structure("AI", items, client=FC(
        "개요: 전체 개요다.\n"
        "[테마] 모델 경쟁 || 경쟁이 치열 || 1,3\n"
        "[테마] 인프라 || 비용이 핵심 || 2\n"
        "[단신] 4\n"
        "관련주제: Claude, GPU"))
    assert out["overview"] == "전체 개요다."
    assert len(out["themes"]) == 2
    assert out["themes"][0]["name"] == "모델 경쟁"
    assert out["themes"][0]["intro"] == "경쟁이 치열"
    assert out["themes"][0]["indexes"] == [1, 3]
    assert out["orphans"] == [4]
    assert out["related"] == ["Claude", "GPU"]
