class _R:
    def __init__(s,c): s.choices=[type("C",(),{"message":type("M",(),{"content":c})})]
class _FC:
    def __init__(s,c): s._c=c; s.chat=type("Ch",(),{"completions":s})()
    def create(s,**k): return _R(s._c)
class _RecFC(_FC):
    """create()에 넘어온 kwargs를 기록하는 페이크."""
    def create(s, **k): s.seen = k; return _R(s._c)

EMPTY_JSON = '{"overview":"x","themes":[],"orphans":[],"related":[]}'


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


def test_synthesize_structure_handles_unclosed_fence():
    # 닫는 펜스가 없어도 JSON을 파싱해야 한다 (Fix 2)
    from collector.wikisynth import synthesize_structure
    items = [{"title":"A","summary":"a"}]
    out = synthesize_structure("AI", items, client=_FC(
        '```json\n{"overview":"x","themes":[],"orphans":[],"related":[]}'))
    assert out["overview"] == "x"


def test_synthesize_structure_no_clients_raises_runtimeerror():
    # 후보 클라이언트가 비면 RuntimeError (TypeError 아님) (Fix 6)
    import pytest
    from collector.wikisynth import synthesize_structure
    with pytest.raises(RuntimeError):
        synthesize_structure("AI", [{"title":"A","summary":"a"}], clients=[])


def test_synthesize_structure_garbage_yields_empty():
    from collector.wikisynth import synthesize_structure
    items = [{"title":"A","summary":"a"}]
    out = synthesize_structure("AI", items, client=_FC(
        "죄송합니다, 정리할 수 없습니다. 항목이 너무 적습니다."))
    assert out["overview"] == ""
    assert out["themes"] == []
    assert out["orphans"] == []
    assert out["related"] == []


# ── #14 항목 단위 truncation + JSON 모드 ─────────────────────────────────

def test_synthesize_includes_only_last_25_items():
    # 문자 단위 [:8000] 절단 대신 최근 25개만 번호 매겨 포함 (오래된 항목이 잘림)
    from collector.wikisynth import synthesize_structure, SYNTH_WINDOW
    assert SYNTH_WINDOW == 25
    items = [{"title": f"T{i}", "summary": f"s{i}"} for i in range(30)]
    fake = _RecFC(EMPTY_JSON)
    synthesize_structure("AI", items, client=fake)
    prompt = fake.seen["messages"][0]["content"]
    assert "T4" not in prompt            # 오래된 항목(앞쪽) 제외
    assert "[1] T5" in prompt            # 윈도우 첫 항목이 번호 1
    assert "[25] T29" in prompt          # 최신 항목이 끝까지 포함 (뒤쪽 절단 없음)
    assert "[26]" not in prompt


def test_synthesize_caps_each_summary_at_400_chars():
    from collector.wikisynth import synthesize_structure
    items = [{"title": "T", "summary": "가" * 1000}]
    fake = _RecFC(EMPTY_JSON)
    synthesize_structure("AI", items, client=fake)
    prompt = fake.seen["messages"][0]["content"]
    assert "가" * 400 in prompt
    assert "가" * 401 not in prompt      # 항목별 400자 캡


def test_synthesize_requests_json_object_response_format():
    from collector.wikisynth import synthesize_structure
    fake = _RecFC(EMPTY_JSON)
    synthesize_structure("AI", [{"title": "A", "summary": "a"}], client=fake)
    assert fake.seen.get("response_format") == {"type": "json_object"}
