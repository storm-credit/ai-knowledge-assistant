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


class _R:
    def __init__(s,c): s.choices=[type("C",(),{"message":type("M",(),{"content":c})})]
class _FC:
    def __init__(s,c): s._c=c; s.chat=type("Ch",(),{"completions":s})()
    def create(s,**k): return _R(s._c)


def test_synthesize_structure_parses_themes_orphans():
    from collector.wikisynth import synthesize_structure
    items = [{"title":"A","summary":"a"},{"title":"B","summary":"b"},
             {"title":"C","summary":"c"},{"title":"D","summary":"d"}]
    out = synthesize_structure("AI", items, client=_FC(
        '{"overview":"전체 개요다.",'
        '"themes":[{"name":"모델 경쟁","intro":"경쟁이 치열","items":[1,3]},'
        '{"name":"인프라","intro":"비용이 핵심","items":[2]}],'
        '"orphans":[4],"related":["Claude","GPU"]}'))
    assert out["overview"] == "전체 개요다."
    assert len(out["themes"]) == 2
    assert out["themes"][0]["name"] == "모델 경쟁"
    assert out["themes"][0]["intro"] == "경쟁이 치열"
    assert out["themes"][0]["indexes"] == [1, 3]
    assert out["orphans"] == [4]
    assert out["related"] == ["Claude", "GPU"]


def test_synthesize_structure_handles_fenced_json():
    from collector.wikisynth import synthesize_structure
    items = [{"title":"A","summary":"a"},{"title":"B","summary":"b"}]
    out = synthesize_structure("AI", items, client=_FC(
        '```json\n'
        '{"overview":"개요.","themes":[{"name":"테마","intro":"정리","items":[1]}],'
        '"orphans":[2],"related":["Claude"]}\n'
        '```'))
    assert out["overview"] == "개요."
    assert out["themes"][0]["indexes"] == [1]
    assert out["orphans"] == [2]


def test_synthesize_structure_garbage_yields_empty():
    from collector.wikisynth import synthesize_structure
    items = [{"title":"A","summary":"a"}]
    out = synthesize_structure("AI", items, client=_FC(
        "죄송합니다, 정리할 수 없습니다. 항목이 너무 적습니다."))
    assert out["overview"] == ""
    assert out["themes"] == []
    assert out["orphans"] == []
    assert out["related"] == []
