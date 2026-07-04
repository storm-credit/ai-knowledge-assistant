"""(#18) 동시 실행 락 — state/.lock 으로 run/wiki/learn 중복 실행 방지."""
import os
import time

from collector.state import acquire_lock, release_lock


def test_acquire_then_second_acquire_fails(tmp_path):
    lock = str(tmp_path / "state" / ".lock")
    assert acquire_lock(lock) is True
    assert os.path.exists(lock)
    assert acquire_lock(lock) is False       # 이미 실행 중 → 획득 실패


def test_release_removes_lock_and_allows_reacquire(tmp_path):
    lock = str(tmp_path / ".lock")
    assert acquire_lock(lock) is True
    release_lock(lock)
    assert not os.path.exists(lock)
    assert acquire_lock(lock) is True


def test_release_missing_lock_is_noop(tmp_path):
    release_lock(str(tmp_path / "없는파일.lock"))   # 예외 없이 통과


def test_stale_lock_is_ignored_and_refreshed(tmp_path):
    # 죽은 실행이 남긴 2시간 이상 지난 락은 무시하고 진행 + mtime 갱신
    lock = str(tmp_path / ".lock")
    assert acquire_lock(lock) is True
    old = time.time() - 3 * 60 * 60
    os.utime(lock, (old, old))
    assert acquire_lock(lock) is True        # 낡은 락 → 진행
    assert os.path.getmtime(lock) > time.time() - 60   # 락 갱신됨


def test_fresh_lock_under_2h_blocks(tmp_path):
    lock = str(tmp_path / ".lock")
    assert acquire_lock(lock) is True
    recent = time.time() - 60 * 60           # 1시간 전 → 아직 유효
    os.utime(lock, (recent, recent))
    assert acquire_lock(lock) is False


# ── main() 통합: 락 걸려 있으면 return 1, 정상 종료 시 락 해제 ────────────

def test_main_returns_1_when_lock_held(tmp_path, monkeypatch, capsys):
    from collector.__main__ import main
    monkeypatch.chdir(tmp_path)
    os.makedirs("state")
    with open("state/.lock", "w") as f:
        f.write("1")
    monkeypatch.setattr("sys.argv", ["collector", "wiki"])
    assert main() == 1
    assert "진행 중" in capsys.readouterr().out
    assert os.path.exists("state/.lock")     # 남의 락은 지우지 않음


def test_main_releases_lock_after_run(tmp_path, monkeypatch):
    from collector.__main__ import main
    monkeypatch.chdir(tmp_path)              # 빈 디렉터리 → wiki가 빈 상태로 무해하게 돎
    monkeypatch.setattr("sys.argv", ["collector", "wiki"])
    assert main() == 0
    assert not os.path.exists("state/.lock")  # finally에서 해제
