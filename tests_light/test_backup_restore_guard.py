"""Safety tests for backup restore guards; no PostgreSQL server is required."""
import hashlib
import os
import subprocess
from pathlib import Path
import re

def bash_script_path(path):
    """Return a script path in the POSIX namespace used by Git Bash/WSL."""
    resolved = Path(path).resolve()
    raw = resolved.as_posix()
    # Git Bash accepts /c/Users/... rather than C:/Users/... .
    match = re.match(r"^([A-Za-z]):/(.*)$", raw)
    if os.name == "nt" and match:
        return f"/{match.group(1).lower()}/{match.group(2)}"
    return raw

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_backup_restore.sh"


def run_restore(tmp_path, *, backup=b"test-backup", checksum=True, target="postgresql://user:pw@localhost:5432/restore", source="postgresql+psycopg://user:pw@localhost:5432/source", confirm="true"):
    backup_path = tmp_path / "backup.dump"
    backup_path.write_bytes(backup)
    if checksum:
        digest = hashlib.sha256(backup).hexdigest()
        (tmp_path / "backup.dump.sha256").write_text(f"{digest}  backup.dump\n", encoding="ascii")
    env = os.environ.copy()
    env.update({
        "BACKUP_FILE": str(backup_path),
        "RESTORE_DATABASE_URL": target,
        "SOURCE_DATABASE_URL": source,
        "RESTORE_CONFIRM_DISPOSABLE": confirm,
    })
    return subprocess.run(["bash", bash_script_path(SCRIPT)], env=env, text=True, capture_output=True, check=False)


def test_restore_refuses_same_database_even_with_different_driver_prefix(tmp_path):
    result = run_restore(
        tmp_path,
        target="postgresql://user:pw@localhost:5432/campus",
        source="postgresql+psycopg://user:pw@localhost:5432/campus",
    )
    assert result.returncode != 0
    assert "source database identity" in result.stderr


def test_restore_requires_disposable_confirmation(tmp_path):
    result = run_restore(tmp_path, confirm="false")
    assert result.returncode == 3
    assert "RESTORE_CONFIRM_DISPOSABLE" in result.stderr


def test_restore_refuses_missing_checksum_before_touching_database(tmp_path):
    result = run_restore(tmp_path, checksum=False)
    assert result.returncode == 6
    assert "checksum sidecar is missing" in result.stderr


def test_restore_refuses_tampered_backup_checksum(tmp_path):
    backup_path = tmp_path / "backup.dump"
    backup_path.write_bytes(b"original")
    digest = hashlib.sha256(b"original").hexdigest()
    (tmp_path / "backup.dump.sha256").write_text(f"{digest}  backup.dump\n", encoding="ascii")
    backup_path.write_bytes(b"tampered")
    env = os.environ.copy()
    env.update({
        "BACKUP_FILE": str(backup_path),
        "RESTORE_DATABASE_URL": "postgresql://user:pw@localhost:5432/restore",
        "SOURCE_DATABASE_URL": "postgresql://user:pw@localhost:5432/source",
        "RESTORE_CONFIRM_DISPOSABLE": "true",
    })
    result = subprocess.run(["bash", bash_script_path(SCRIPT)], env=env, text=True, capture_output=True, check=False)
    assert result.returncode != 0
    assert "FAILED" in result.stdout or "checksum" in result.stderr.lower()
