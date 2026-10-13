# CampusRipple data governance and release checklist

This document is an operational checklist, not a substitute for ACE Engineering College's approved policies or legal review.

## Data minimization and access

- Import only fields necessary for timetable, room, course, attendance, and workflow use.
- Never import passwords, payment-card data, personal health records, or unrelated student records.
- Use institution-issued service credentials with read-only permissions and rotate/revoke them through the institution's process.
- Restrict administrative accounts to named, authorized staff. Review role assignments periodically.
- Test that students can only access their own private decisions and permitted records; use synthetic accounts for tests.
- Do not include API tokens, reset tokens, verification tokens, or raw authentication secrets in logs or reports.

## Retention and deletion

Before production, the institution's data owner must approve retention periods for audit events, attendance, timetable snapshots, user-submitted scenarios, feedback, and backups. Implement deletion jobs only after the policy and legal holds are approved. Ensure deletion includes backups according to the approved lifecycle and retain only what is necessary for audit/legal requirements.

## Production release gates

- [ ] Approved privacy notice, data owner, support contact, and incident process.
- [ ] HTTPS enabled; strong unique `SECRET_KEY`; secure cookies; proxy headers trusted only behind a correctly configured proxy.
- [ ] SMTP verification and reset flows tested with controlled accounts.
- [ ] Institution API contract, token scope, data mapping, rate limits, and sync schedule approved.
- [ ] PostgreSQL migrations tested against a restored production-like backup.
- [ ] Full pytest suite and PostgreSQL trigger tests pass in CI.
- [ ] Manual/browser role and workflow checks pass in staging.
- [ ] Backup restoration drill succeeds and encrypted off-site backup location is configured.
- [ ] Monitoring and alert delivery tested; secrets excluded from logs.
- [ ] Load test results documented at 50, 100, 250, and 500 virtual users; capacity claims match measured results.
- [ ] Rollback plan and accountable operator identified.

## Prediction-quality feedback

Impact reviews are human-reported observations. They are useful for triage and evaluation, but are not automatically verified ground truth. A model-quality report must disclose the sample size, reviewer coverage, analysis rule version, time period, missing outcomes, and any sampling bias. Do not report the fraction marked Confirmed as model accuracy without independent validation and a defined evaluation protocol.

## External dependencies

Live college ERP/SIS data, institutional SSO, SMTP delivery, hosting resources, and monitoring providers require accounts, credentials, approvals, and configuration outside this repository. Never substitute synthetic data for official data without an explicit demo label.
