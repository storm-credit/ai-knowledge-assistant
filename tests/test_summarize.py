from collector.models import Item
from collector.summarize import summarize_item

class FakeResp:
    def __init__(self, content):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})})]

class FakeClient:
    def __init__(self, content):
        self._content = content
        self.chat = type("Chat", (), {"completions": self})()
    def create(self, **kwargs):
        return FakeResp(self._content)

class Quota429Client:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": self})()
    def create(self, **kwargs):
        raise Exception("Error code: 429 - RESOURCE_EXHAUSTED quota exceeded")

def test_summarize_fills_summary_field():
    it = Item(source_name="조코딩", source_type="youtube", id="x",
              title="제목", link="l", published="", raw_text="긴 원문")
    fake = FakeClient("- 핵심 요약 한 줄")
    out = summarize_item(it, client=fake, model="gemini-2.5-flash")
    assert "핵심 요약" in out.summary

def test_summarize_rotates_to_next_key_on_quota():
    it = Item(source_name="조코딩", source_type="youtube", id="x",
              title="제목", link="l", published="", raw_text="긴 원문")
    # 첫 키는 429(쿼터 초과), 두 번째 키로 넘어가 성공해야 함
    out = summarize_item(it, clients=[Quota429Client(), FakeClient("- 두번째 키 성공")])
    assert "두번째 키 성공" in out.summary

def test_summarize_raises_when_all_keys_exhausted():
    it = Item(source_name="조코딩", source_type="youtube", id="x",
              title="제목", link="l", published="", raw_text="긴 원문")
    try:
        summarize_item(it, clients=[Quota429Client(), Quota429Client()])
        assert False, "모든 키 소진 시 예외가 나야 함"
    except Exception as e:
        assert "429" in str(e)
