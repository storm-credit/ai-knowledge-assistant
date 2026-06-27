from collector.config import SourcesConfig, Source
from collector.models import Item
from collector.state import StateStore
from collector.pipeline import run
from collector.store import load_items

def test_run_appends_new_items_to_store(tmp_path):
    cfg = SourcesConfig(youtube=[], newsletters=[Source(name="SaaStr", rss="x", type="newsletter")])
    state = StateStore(str(tmp_path / "seen.json"))
    store_path = str(tmp_path / "items.jsonl")

    def fake_fetch(src):
        return [Item(source_name=src.name, source_type=src.type, id="n1",
                     title="새글", link="l", published="", raw_text="원문")]
    def fake_sum(it): it.summary = "요약"; return it

    run(cfg, state, out_dir=str(tmp_path/"out"), date="2026-06-27",
        fetch=fake_fetch, summarize=fake_sum, enrich=lambda i: i,
        sleep=lambda *_: None, items_store=store_path)

    saved = load_items(store_path)
    assert len(saved) == 1 and saved[0].id == "n1" and saved[0].summary == "요약"
