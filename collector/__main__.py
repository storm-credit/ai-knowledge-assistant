import sys, datetime
from .config import load_sources
from .state import StateStore
from .pipeline import run
from .wiki import run_wiki

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    today = datetime.date.today().isoformat()
    if cmd in ("run", "all"):
        cfg = load_sources("sources.yaml")
        state = StateStore("state/seen.json")
        run(cfg, state, out_dir="notes/daily", date=today)
        run_wiki()                      # 수집 후 위키 갱신
    elif cmd == "wiki":
        run_wiki()
    else:
        print(f"알 수 없는 명령: {cmd} (run | wiki)")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
