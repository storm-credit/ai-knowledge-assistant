def test_load_categories_from_file_and_default(tmp_path, monkeypatch):
    from collector import classify
    # 파일 있으면 그걸 사용
    p = tmp_path / "categories.yaml"
    p.write_text("categories:\n  - 가\n  - 나\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert classify.load_categories() == ["가", "나"]
    # 파일 없으면 기본 상수
    (tmp_path / "categories.yaml").unlink()
    assert classify.load_categories() == classify.CATEGORIES
