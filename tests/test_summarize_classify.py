from collector.models import Item
from collector.summarize import summarize_and_classify

class FakeResp:
    def __init__(self, c): self.choices=[type("C",(),{"message":type("M",(),{"content":c})})]
class FakeClient:
    def __init__(self, c): self._c=c; self.chat=type("Ch",(),{"completions":self})()
    def create(self, **k): return FakeResp(self._c)

def _item():
    return Item(source_name="조코딩", source_type="youtube", id="x",
                title="AI 에이전트 시대", link="l", published="", raw_text="원문")

def test_summary_and_categories_parsed_and_filtered():
    fake = FakeClient("요약 첫줄\n요약 둘째줄\n카테고리: AI 모델·기술, 엉뚱")
    out = summarize_and_classify(_item(), client=fake)
    assert "요약 첫줄" in out.summary
    assert "카테고리" not in out.summary
    assert out.categories == ["AI 모델·기술"]   # 유효하지 않은 카테고리 제거

def test_no_valid_category_defaults_to_etc():
    fake = FakeClient("요약만 있고\n카테고리: 엉뚱한것")
    out = summarize_and_classify(_item(), client=fake)
    assert "요약만 있고" in out.summary
    assert out.categories == ["기타"]

def test_combined_keeps_multiline_bullet_summary():
    from collector.models import Item
    from collector.summarize import summarize_and_classify
    class R:
        def __init__(s,c): s.choices=[type("C",(),{"message":type("M",(),{"content":c})})]
    class FC:
        def __init__(s,c): s._c=c; s.chat=type("Ch",(),{"completions":s})()
        def create(s,**k): return R(s._c)
    it = Item(source_name="노정석", source_type="youtube", id="x",
              title="EP100", link="l", published="2026-06-27", raw_text="원문")
    fake = FC("- 포인트 하나\n- 포인트 둘\n- 포인트 셋\n카테고리: AI 모델·기술")
    out = summarize_and_classify(it, client=fake)
    assert "포인트 하나" in out.summary and "포인트 셋" in out.summary
    assert "카테고리" not in out.summary          # 카테고리 줄은 요약서 제외
    assert out.categories == ["AI 모델·기술"]
