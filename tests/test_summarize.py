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

def test_summarize_fills_summary_field():
    it = Item(source_name="조코딩", source_type="youtube", id="x",
              title="제목", link="l", published="", raw_text="긴 원문")
    fake = FakeClient("- 핵심 요약 한 줄")
    out = summarize_item(it, client=fake, model="gemini-2.5-flash")
    assert "핵심 요약" in out.summary
