from collector.models import Item
from collector.enrich import enrich_youtube

def make_item():
    return Item(source_name="조코딩", source_type="youtube",
                id="yt", title="t", link="https://www.youtube.com/watch?v=VID",
                published="", raw_text="원래 설명")

def test_enrich_uses_transcript_when_available():
    it = enrich_youtube(make_item(), fetch_transcript=lambda vid: "자막 내용 " + vid)
    assert "자막 내용 VID" in it.raw_text

def test_enrich_falls_back_to_description_on_failure():
    def boom(vid): raise RuntimeError("no captions")
    it = enrich_youtube(make_item(), fetch_transcript=boom)
    assert it.raw_text == "원래 설명"
