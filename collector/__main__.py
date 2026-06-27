import sys, datetime
from .config import load_sources
from .state import StateStore
from .pipeline import run
from .wiki import run_wiki

def main():
    args = sys.argv[1:]
    cmd = args[0] if args and not args[0].startswith("-") else "run"
    force_resynth = "--resynth" in args
    threshold = 0 if force_resynth else 5   # 0 → 모든 주제 개요 강제 재합성
    today = datetime.date.today().isoformat()
    if cmd in ("run", "all"):
        cfg = load_sources("sources.yaml")
        state = StateStore("state/seen.json")
        run(cfg, state, out_dir="notes/daily", date=today)
        run_wiki(resynth_threshold=threshold)   # 수집 후 위키 갱신
    elif cmd == "wiki":
        run_wiki(resynth_threshold=threshold)
    else:
        print(f"알 수 없는 명령: {cmd} (run | wiki)")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
