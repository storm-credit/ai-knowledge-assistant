from collector.models import Item

def test_item_holds_fields_and_summary_defaults_empty():
    it = Item(source_name="조코딩", source_type="youtube",
              id="yt:abc", title="제목", link="http://x", published="2026-06-27",
              raw_text="원문")
    assert it.summary == ""
    assert it.tags == []
    assert it.id == "yt:abc"
