"""Regression tests for the local bootstrap email policy without importing Flask."""
import ast
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TREE = ast.parse((ROOT / "app" / "routes.py").read_text(encoding="utf-8"))
node = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == "is_eligible_college_email")
namespace = {"os": os, "re": re, "ALLOWED_EMAIL_DOMAIN": "aceec.ac.in"}
exec(compile(ast.Module(body=[node], type_ignores=[]), "routes.py", "exec"), namespace)
eligible = namespace["is_eligible_college_email"]


def test_aceec_email_allowed():
    os.environ["APP_ENV"] = "development"
    assert eligible("student@aceec.ac.in")


def test_local_bootstrap_email_allowed_only_outside_production():
    os.environ["APP_ENV"] = "development"
    assert eligible("admin@localhost.test")
    os.environ["APP_ENV"] = "production"
    assert not eligible("admin@localhost.test")


def test_unapproved_domain_stays_blocked():
    os.environ["APP_ENV"] = "development"
    assert not eligible("admin@gmail.com")
