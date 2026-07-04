import sys, datetime

# Windows 콘솔(cp949)에서 이모지/특수문자 print 시 죽는 것 방지
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from .config import load_sources
from .state import StateStore, acquire_lock, release_lock
from .pipeline import run
from .wiki import run_wiki

def _dispatch(cmd, args):
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
    elif cmd == "learn":
        # 적용형 학습 노트 (docs/14): python -m collector learn "하네스 엔지니어링"
        concept = next((a for a in args[1:] if not a.startswith("-")), None)
        if not concept:
            print('사용법: python -m collector learn "<개념>"')
            return 1
        from .learn import run_learn
        if run_learn(concept, date=today) is None:
            return 1   # 예산 부족 등으로 미룸
    return 0

def main():
    args = sys.argv[1:]
    cmd = args[0] if args and not args[0].startswith("-") else "run"
    if cmd not in ("run", "all", "wiki", "learn"):
        print(f"알 수 없는 명령: {cmd} (run | wiki | learn)")
        return 1
    # 동시 실행 방지 (#18): cron과 수동 실행이 겹치면 state 파일이 서로 깨진다
    if not acquire_lock():
        print("다른 실행 진행 중 (state/.lock) — 종료")
        return 1
    try:
        return _dispatch(cmd, args)
    finally:
        release_lock()

if __name__ == "__main__":
    sys.exit(main())
