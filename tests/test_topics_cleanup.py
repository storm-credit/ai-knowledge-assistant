import os
from collector.models import Item
from collector.topics import TopicStore, write_pages, MEMO_START, MEMO_END, DEFAULT_MEMO

def test_write_pages_removes_stale_keeps_index(tmp_path):
    out = tmp_path / "topics"
    out.mkdir()
    # 우리가 생성했던(기본 메모) 스테일 페이지 = 삭제 대상
    (out / "옛주제.md").write_text(
        f"# 옛주제\n\n{MEMO_START}\n{DEFAULT_MEMO}\n{MEMO_END}\n", encoding="utf-8")
    (out / "00-목차.md").write_text("idx", encoding="utf-8")  # 목차 (보존)

    s = TopicStore(str(tmp_path / "t.json"))
    s.add_item("AI 모델·기술", Item(source_name="조코딩", source_type="x", id="a",
               title="글a", link="http://a", published="2026-06-27", summary="요약"))
    write_pages(s, str(out))

    files = set(os.listdir(out))
    assert "AI 모델·기술.md" in files   # 현재 주제 생성됨
    assert "옛주제.md" not in files      # 스테일 삭제됨
    assert "00-목차.md" in files        # 목차 보존됨


def test_cleanup_preserves_user_memo_and_foreign(tmp_path):
    # 사용자 메모가 있는 페이지/외부 파일은 정리 루프가 삭제하면 안 됨 (Fix 3)
    from collector.topics import MEMO_START, MEMO_END, DEFAULT_MEMO
    out = tmp_path / "topics"
    out.mkdir()
    # 사용자가 메모를 남긴 (현재 store에 없는) 생성 페이지
    (out / "OldTopic.md").write_text(
        f"# OldTopic\n\n## 메모\n{MEMO_START}\n사용자 메모\n{MEMO_END}\n", encoding="utf-8")
    # 메모 마커가 없는 외부/사용자 파일
    (out / "scratch.md").write_text("내가 만든 잡다한 노트", encoding="utf-8")
    # 기본 메모만 가진 스테일 생성 페이지 (삭제 대상)
    (out / "StaleGen.md").write_text(
        f"# StaleGen\n\n{MEMO_START}\n{DEFAULT_MEMO}\n{MEMO_END}\n", encoding="utf-8")

    s = TopicStore(str(tmp_path / "t.json"))
    s.add_item("AI 모델·기술", Item(source_name="조코딩", source_type="x", id="a",
               title="글a", link="http://a", published="2026-06-27", summary="요약"))
    write_pages(s, str(out))

    files = set(os.listdir(out))
    assert "OldTopic.md" in files     # 사용자 메모 보존
    assert "scratch.md" in files      # 외부 파일 보존
    assert "StaleGen.md" not in files # 기본 메모 스테일은 삭제됨
