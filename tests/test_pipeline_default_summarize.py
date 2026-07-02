from collector.config import SourcesConfig, Source
from collector.models import Item
from collector.state import StateStore
from collector.pipeline import run
from collector.store import load_items
import collector.llm as llm_mod

class FakeResp:
    def __init__(self, c): self.choices=[type("C",(),{"message":type("M",(),{"content":c})})]
class FakeClient:
    def __init__(self, c): self._c=c; self.chat=type("Ch",(),{"completions":self})()
    def create(self, **k): return FakeResp(self._c)

def test_default_summarize_also_classifies(tmp_path, monkeypatch):
    # 기본 summarize는 summarize_and_classify → 요약+카테고리 둘 다 채워짐 (LLM 1콜)
    monkeypatch.setattr(llm_mod, "_default_clients",
                        lambda: [FakeClient("요약 본문\n카테고리: AI 모델·기술")])
    # 미주입 경로는 모듈 기본 예산을 쓰므로 실제 state/ 파일을 건드리지 않게 tmp로 격리
    monkeypatch.setattr(llm_mod, "_default_budget",
                        llm_mod.CallBudget(str(tmp_path / "budget.json")))
    monkeypatch.setattr(llm_mod, "_default_breaker", llm_mod.CircuitBreaker())
    cfg = SourcesConfig(youtube=[], newsletters=[Source(name="SaaStr", rss="x", type="newsletter")])
    state = StateStore(str(tmp_path / "seen.json"))
    store_path = str(tmp_path / "items.jsonl")

    def fake_fetch(src):
        return [Item(source_name=src.name, source_type=src.type, id="n1",
                     title="새글", link="l", published="", raw_text="원문")]

    # summarize 인자를 주입하지 않음 → 기본값 사용
    run(cfg, state, out_dir=str(tmp_path/"out"), date="2026-06-27",
        fetch=fake_fetch, enrich=lambda i: i,
        sleep=lambda *_: None, items_store=store_path)

    saved = load_items(store_path)
    assert len(saved) == 1
    assert "요약 본문" in saved[0].summary
    assert saved[0].categories == ["AI 모델·기술"]
