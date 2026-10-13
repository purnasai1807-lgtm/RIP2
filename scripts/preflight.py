"""Deployment preflight checks for CampusRipple.

This checks configuration and optionally database connectivity. It does not prove
that SMTP delivers mail, that the institutional API is authorized, or that the
application has passed a load/security review.
"""
from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import urlparse

PLACEHOLDER_MARKERS = ("replace-with", "change_me", "changeme", "example.com", "example.edu", "your-smtp", "example-password")


def check_configuration(env: dict[str, str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    production = env.get("APP_ENV", "development").strip().lower() == "production"
    secret = env.get("SECRET_KEY", "")
    database_url = env.get("DATABASE_URL", "")
    secure_cookie = env.get("COOKIE_SECURE", "false").strip().lower() == "true"
    require_verification = env.get("REQUIRE_EMAIL_VERIFICATION", "true" if production else "false").strip().lower() == "true"
    public_url = env.get("PUBLIC_BASE_URL", "")
    mail_server = env.get("MAIL_SERVER", "")
    mail_sender = env.get("MAIL_DEFAULT_SENDER", "")
    domains = [x.strip().lower().lstrip("@") for x in env.get("INSTITUTIONAL_EMAIL_DOMAINS", "").split(",") if x.strip()]

    if production:
        if len(secret) < 32 or any(marker in secret.lower() for marker in PLACEHOLDER_MARKERS):
            errors.append("SECRET_KEY must be a unique, random secret with at least 32 characters.")
        if not database_url.startswith(("postgresql+psycopg://", "postgresql://")):
            errors.append("Production DATABASE_URL must point to PostgreSQL using a supported SQLAlchemy URL.")
        if not secure_cookie:
            errors.append("Set COOKIE_SECURE=true and terminate public traffic at HTTPS.")
        if domains != ["aceec.ac.in"]:
            errors.append("INSTITUTIONAL_EMAIL_DOMAINS must be exactly aceec.ac.in; only @aceec.ac.in accounts are eligible.")
        if require_verification:
            if not mail_server or not mail_sender or not env.get("MAIL_PASSWORD"):
                errors.append("Email verification requires MAIL_SERVER, MAIL_DEFAULT_SENDER, and MAIL_PASSWORD.")
            elif any(marker in value.lower() for value in (mail_server, mail_sender, env.get("MAIL_PASSWORD", "")) for marker in PLACEHOLDER_MARKERS):
                errors.append("SMTP configuration contains placeholder values; configure real provider settings and an app password.")
            parsed = urlparse(public_url)
            if parsed.scheme != "https" or not parsed.netloc or any(marker in public_url.lower() for marker in PLACEHOLDER_MARKERS) or "localhost" in parsed.hostname.lower():
                errors.append("Email verification requires PUBLIC_BASE_URL to be the real public HTTPS URL.")
        if env.get("TRUST_PROXY_HEADERS", "false").lower() == "true":
            warnings.append("TRUST_PROXY_HEADERS=true: verify the proxy strips and rewrites forwarded headers.")
    else:
        if not secret or secret == "dev-only-change-this-secret":
            warnings.append("Set a local SECRET_KEY before using accounts outside disposable development.")
        if require_verification and not (mail_server and mail_sender and env.get("MAIL_PASSWORD")):
            errors.append("REQUIRE_EMAIL_VERIFICATION=true but SMTP configuration is incomplete.")

    api_url = env.get("COLLEGE_DATA_API_URL", "").strip()
    api_token = env.get("COLLEGE_DATA_API_TOKEN", "").strip()
    if bool(api_url) != bool(api_token):
        errors.append("COLLEGE_DATA_API_URL and COLLEGE_DATA_API_TOKEN must either both be set or both be empty.")
    if api_url:
        parsed_api = urlparse(api_url)
        if parsed_api.scheme != "https" or not parsed_api.hostname or parsed_api.username or parsed_api.password or parsed_api.fragment:
            errors.append("COLLEGE_DATA_API_URL must be an HTTPS URL without embedded credentials or fragments.")
        if any(marker in api_token.lower() for marker in PLACEHOLDER_MARKERS):
            errors.append("COLLEGE_DATA_API_TOKEN appears to be a placeholder.")
    elif production:
        warnings.append("Official college timetable API is not configured; imported/manual data only will be available.")

    if production and env.get("REQUIRE_EMAIL_VERIFICATION", "true").lower() == "false":
        warnings.append("Email verification is disabled in production. Confirm that this is explicitly approved.")
    return errors, warnings


def check_database(database_url: str) -> str | None:
    if not database_url:
        return "DATABASE_URL is unset; the application will use its configured default database."
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5} if database_url.startswith(("postgresql://", "postgresql+psycopg://")) else {})
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
        return None
    except Exception as exc:  # report class only, never secrets or connection string
        return f"Database connectivity check failed ({type(exc).__name__}). Check the URL, network, credentials, and database status."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-database", action="store_true", help="also verify DATABASE_URL can execute SELECT 1")
    args = parser.parse_args()
    errors, warnings = check_configuration(dict(os.environ))
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    if args.check_database:
        error = check_database(os.environ.get("DATABASE_URL", ""))
        if error:
            errors.append(error)
        else:
            print("PASS: database connection and SELECT 1")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"Preflight failed with {len(errors)} error(s).", file=sys.stderr)
        return 1
    print("Preflight configuration checks passed. This is not a substitute for integration, browser, restore, or load testing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
