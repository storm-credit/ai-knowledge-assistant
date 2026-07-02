import pytest
from collector.models import Item
from collector.classify import classify_item, CATEGORIES

class FakeResp:
    def __init__(self, c): self.choices=[type("C",(),{"message":type("M",(),{"content":c})})]
class FakeClient:
    def __init__(self, c): self._c=c; self.chat=type("Ch",(),{"completions":self})()
    def create(self, **k): return FakeResp(self._c)

# classify_item은 내부에서 load_categories()로 cwd의 categories.yaml을 읽으므로
# 실제 파일에 결합되지 않게 tmp_path에 고정 yaml을 두고 chdir로 격리한다.
FIXED_YAML = ("categories:\n"
              "  - AI 모델·기술\n"
              "  - AI 비즈니스·투자\n"
              "  - AI 활용·도구\n"
              "  - 기타\n")

@pytest.fixture
def isolated_cats(tmp_path, monkeypatch):
    (tmp_path / "categories.yaml").write_text(FIXED_YAML, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

def _item():
    return Item(source_name="조코딩", source_type="youtube", id="x",
                title="AI 에이전트 시대", link="l", published="", summary="에이전트 요약")

def test_categories_constant():
    assert CATEGORIES == ["AI 모델·기술", "AI 비즈니스·투자", "AI 활용·도구",
                          "한국 AI·스타트업", "인프라·에너지", "인재·일의 미래", "기타"]

def test_classify_filters_to_valid_categories(isolated_cats):
    out = classify_item(_item(), client=FakeClient("AI 모델·기술, 엉뚱한것"))
    assert out == ["AI 모델·기술"]   # 유효하지 않은 카테고리는 제거

def test_classify_all_invalid_returns_etc(isolated_cats):
    out = classify_item(_item(), client=FakeClient("엉뚱한것, 또다른엉뚱"))
    assert out == ["기타"]

def test_classify_strips_category_prefix(isolated_cats):
    # 모델이 '카테고리: X' 형식으로 답해도 헬퍼로 파싱된다
    out = classify_item(_item(), client=FakeClient("카테고리: AI 모델·기술"))
    assert out == ["AI 모델·기술"]


def test_classify_no_clients_raises_runtimeerror(isolated_cats):
    # 키/클라이언트가 비면 RuntimeError (TypeError 아님) (Fix 6)
    with pytest.raises(RuntimeError):
        classify_item(_item(), clients=[])


def test_classify_handles_none_body(isolated_cats):
    # summary 빈 문자열, raw_text None 이어도 TypeError 없이 분류 (Fix 7)
    item = Item(source_name="s", source_type="youtube", id="x",
                title="AI 모델 발표", link="l", published="", summary="", raw_text=None)
    out = classify_item(item, client=FakeClient("AI 모델·기술"))
    assert out == ["AI 모델·기술"]


def test_classify_max_two_valid(isolated_cats):
    out = classify_item(_item(),
                        client=FakeClient("AI 모델·기술, AI 비즈니스·투자, AI 활용·도구"))
    assert out == ["AI 모델·기술", "AI 비즈니스·투자"]   # 최대 2개
