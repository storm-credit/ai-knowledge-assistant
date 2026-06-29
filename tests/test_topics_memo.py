import os
from collector.models import Item
from collector.topics import TopicStore, write_pages, MEMO_START, MEMO_END

def test_memo_preserved_across_regen(tmp_path):
    out = tmp_path / "topics"
    s = TopicStore(str(tmp_path / "t.json"))
    s.add_item("AI", Item(source_name="s", source_type="x", id="a", title="T",
               link="http://a", published="2026-06-29", summary="요약"))
    write_pages(s, str(out))
    p = out / "AI.md"
    txt = p.read_text(encoding="utf-8")
    assert MEMO_START in txt and MEMO_END in txt            # 메모 구역 존재
    # 사용자가 메모 작성
    edited = txt.replace(txt[txt.find(MEMO_START)+len(MEMO_START):txt.find(MEMO_END)],
                         "\n내가 적은 메모\n")
    p.write_text(edited, encoding="utf-8")
    # 재생성
    write_pages(s, str(out))
    txt2 = p.read_text(encoding="utf-8")
    assert "내가 적은 메모" in txt2                          # 보존됨


def test_blank_memo_preserved_across_regen(tmp_path):
    # 사용자가 메모를 비워두면 빈 채로 유지 (DEFAULT_MEMO 재삽입 금지) (Fix 8)
    from collector.topics import DEFAULT_MEMO, _extract_memo
    out = tmp_path / "topics"
    s = TopicStore(str(tmp_path / "t.json"))
    s.add_item("AI", Item(source_name="s", source_type="x", id="a", title="T",
               link="http://a", published="2026-06-29", summary="요약"))
    write_pages(s, str(out))
    p = out / "AI.md"
    txt = p.read_text(encoding="utf-8")
    # 사용자가 메모를 비움
    edited = txt.replace(txt[txt.find(MEMO_START)+len(MEMO_START):txt.find(MEMO_END)], "\n\n")
    p.write_text(edited, encoding="utf-8")
    # 재생성
    write_pages(s, str(out))
    txt2 = p.read_text(encoding="utf-8")
    assert DEFAULT_MEMO not in txt2          # 기본 메모가 다시 들어오지 않음
    assert _extract_memo(txt2) == ""         # 빈 메모 유지
