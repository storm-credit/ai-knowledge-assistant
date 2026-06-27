import sys, datetime
from .config import load_sources
from .state import StateStore
from .pipeline import run

def main():
    cfg = load_sources("sources.yaml")
    state = StateStore("state/seen.json")
    today = datetime.date.today().isoformat()
    run(cfg, state, out_dir="notes/daily", date=today)

if __name__ == "__main__":
    sys.exit(main())
