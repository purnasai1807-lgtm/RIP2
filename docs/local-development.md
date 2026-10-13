# CampusRipple local development guide

## Fastest path: Docker Desktop

1. Install and start Docker Desktop (Docker Engine + Compose v2).
2. From the repository root run `./scripts/run_local.sh` on Linux/macOS/Git Bash, or run the equivalent PowerShell commands:

   ```powershell
   Copy-Item .env.local.example .env
   docker compose -f docker-compose.local.yml up --build -d
   ```

3. Wait for the `web` container to become healthy. Inspect `docker compose -f docker-compose.local.yml logs -f web` if it does not start.
4. Open `http://localhost:8000`. Verify `http://localhost:8000/healthz` returns HTTP 200 and `{"status":"ok","database":"reachable"}`.
5. Create an administrator from the trusted local terminal:

   ```bash
   docker compose -f docker-compose.local.yml exec web flask --app wsgi:app create-admin admin@localhost.test
   ```

   Use a unique local password when prompted. Then register a separate student account to exercise least-privilege access.
6. Stop the app with `./scripts/stop_local.sh` or `docker compose -f docker-compose.local.yml down`.

The named database volume persists between restarts. `docker compose -f docker-compose.local.yml down -v` permanently deletes this local database; only use it when you intentionally want a clean reset.

## Local-only profile safety

`docker-compose.local.yml` intentionally uses HTTP, disables email verification, and uses placeholder development secrets. It must only be bound to a trusted local machine and must never be exposed to the internet. Production must use the regular production configuration, HTTPS, a strong secret, managed PostgreSQL, real SMTP, the approved institutional email-domain allowlist, and an approved official-data API contract.

## Checks to run before sharing changes

```bash
python -m compileall -q app migrations tests scripts
python scripts/validate_migration_graph.py
python scripts/preflight.py
python -m pytest -q
python scripts/demo_impact_analysis.py path/to/authorized-real-input.json  # requires authorized real data; no bundled sample
```

The complete pytest suite needs the packages in `requirements.txt`. The PostgreSQL guard/concurrency scripts require a disposable PostgreSQL database and the `DATABASE_URL` environment variable. Browser tests require the optional packages in `requirements-browser-test.txt`, an HTTPS staging URL, and a dedicated synthetic account. SMTP testing requires real provider configuration and an explicitly controlled `SMTP_TEST_RECIPIENT`. Do not treat static checks or demo output as evidence that these external integrations work.
