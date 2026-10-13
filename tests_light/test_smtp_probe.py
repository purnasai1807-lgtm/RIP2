"""Offline regression tests for the SMTP probe's configuration handling."""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_smtp.py"


def run_probe(overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith(("MAIL_", "SMTP_"))}
    env.update(overrides)
    return subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, env=env,
                          text=True, capture_output=True, timeout=10, check=False)


def test_smtp_probe_rejects_conflicting_ssl_modes_before_connecting():
    result = run_probe({
        "MAIL_SERVER": "127.0.0.1", "MAIL_PORT": "1025",
        "MAIL_USE_TLS": "true", "MAIL_USE_SSL": "true",
        "MAIL_DEFAULT_SENDER": "test@example.invalid",
        "SMTP_TEST_RECIPIENT": "test@example.invalid",
        "SMTP_ALLOW_NO_AUTH": "true",
    })
    assert result.returncode == 2
    assert "enable only one" in result.stderr


def test_smtp_probe_allows_no_auth_local_sink_without_missing_key_error():
    # Port 1 should refuse immediately; the purpose is to ensure the no-auth path
    # handles absent MAIL_USERNAME/MAIL_PASSWORD without raising KeyError.
    result = run_probe({
        "MAIL_SERVER": "127.0.0.1", "MAIL_PORT": "1",
        "MAIL_USE_TLS": "false", "MAIL_USE_SSL": "false", "MAIL_TIMEOUT": "1",
        "MAIL_DEFAULT_SENDER": "test@example.invalid",
        "SMTP_TEST_RECIPIENT": "test@example.invalid",
        "SMTP_ALLOW_NO_AUTH": "true",
    })
    assert result.returncode == 1
    assert "FAIL: SMTP probe failed" in result.stderr
    assert "KeyError" not in result.stderr


def test_smtp_probe_rejects_invalid_timeout():
    result = run_probe({
        "MAIL_SERVER": "127.0.0.1", "MAIL_PORT": "1025",
        "MAIL_USE_TLS": "false", "MAIL_USE_SSL": "false", "MAIL_TIMEOUT": "0",
        "MAIL_DEFAULT_SENDER": "test@example.invalid",
        "SMTP_TEST_RECIPIENT": "test@example.invalid",
        "SMTP_ALLOW_NO_AUTH": "true",
    })
    assert result.returncode == 2
    assert "MAIL_TIMEOUT must be between" in result.stderr
