# CampusRipple: Vercel + Neon setup

This repository has been adjusted so Vercel defaults to production mode, and the app can use the common PostgreSQL environment-variable names exposed by Neon/Vercel. You still must enter your own secrets and service credentials in the Vercel dashboard; they cannot be safely guessed or generated inside this source archive.

## Vercel project settings

- Framework preset: **Flask**
- Root directory: `./`
- Add the variables below under **Settings → Environment Variables**, selecting **Production** (and Preview if you want preview deployments to use the same services).

## Required variables

| Name | Value/source |
|---|---|
| `APP_ENV` | `production` |
| `DATABASE_URL` | Neon Console → project → **Connect** → copy the **pooled** PostgreSQL connection string. Keep it secret. |
| `SECRET_KEY` | Generate locally with `python -c "import secrets; print(secrets.token_hex(32))"`; paste the output as the value. Never commit it. |
| `COOKIE_SECURE` | `true` |
| `REQUIRE_EMAIL_VERIFICATION` | Optional. SMTP is not required: if `MAIL_SERVER` is not set, email verification is off by default. Set `MAIL_*` variables to turn it on. |
| `INSTITUTIONAL_EMAIL_DOMAINS` | `aceec.ac.in` (the application enforces this domain in code). |
| `PUBLIC_BASE_URL` | Your deployed public HTTPS URL, e.g. `https://your-project.vercel.app` (replace with your real URL). |

The app will also recognize `POSTGRES_URL`, `POSTGRES_PRISMA_URL`, `POSTGRES_URL_NON_POOLING`, `DATABASE_URL_UNPOOLED`, and other common Neon/Vercel PostgreSQL names as fallbacks. Prefer setting `DATABASE_URL` explicitly to a pooled URL.

## Email verification

If `REQUIRE_EMAIL_VERIFICATION=true`, configure real SMTP values:

- `MAIL_SERVER`: your email provider's SMTP host
- `MAIL_PORT`: usually `587` for STARTTLS
- `MAIL_USE_TLS`: `true` for STARTTLS
- `MAIL_USE_SSL`: `false` for STARTTLS (do not enable TLS and SSL together unless your provider explicitly requires it)
- `MAIL_USERNAME`: your SMTP username
- `MAIL_PASSWORD`: your provider's SMTP/app password
- `MAIL_DEFAULT_SENDER`: a sender address authorized by your provider, such as `CampusRipple <no-reply@your-domain>`

Do not use example credentials. If you don't have SMTP configured yet, you can temporarily set `REQUIRE_EMAIL_VERIFICATION=false` only for a private demo, understanding that this disables the verification requirement. Do not use this as a production security shortcut.

## After changing variables

1. Save all variables.
2. Open **Deployments** and redeploy the latest deployment so the new values are loaded.
3. If the app still fails, inspect the failed deployment's **Functions / Runtime Logs** and fix the first traceback error.
4. Apply database migrations from a trusted local environment or CI connected to the same database: `flask --app wsgi:app db upgrade`. Do not run migrations automatically on every serverless request.

Never paste database URLs, passwords, SMTP passwords, or `SECRET_KEY` into chat or commit them to GitHub.
