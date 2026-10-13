# Hackathon submission and acceptance checklist

## Product walkthrough
- [ ] Fresh install starts from documented instructions.
- [ ] Student registration and login work.
- [ ] Scenario create, edit, analyze, compare, detail, and export work.
- [ ] Impact sources distinguish hypotheses from application-record evidence.
- [ ] Student cannot view another user's private scenario.
- [ ] Coordinator/admin review and audit trail work.
- [ ] Responsive layout is checked at desktop and mobile widths.
- [ ] Empty states and validation errors are demonstrated.

## Reliability and security
- [ ] Full dependency installation and `pytest -q` pass in a clean environment.
- [ ] PostgreSQL migrations and conflict/concurrency scripts pass against disposable PostgreSQL.
- [ ] Backup is restored into a separate disposable database.
- [ ] SMTP verification and password reset reach a controlled test inbox.
- [ ] Production secrets are in the hosting secret manager and not in Git.
- [ ] HTTPS and secure cookie configuration are confirmed on staging.
- [ ] Role-based browser acceptance is recorded.
- [ ] Any public integration is authorized, read-only where appropriate, and reconciled with the source owner.

## Evidence and claims
- [ ] Impact validation cases are reviewed by domain stakeholders.
- [ ] Accuracy metrics are computed from a held-out reviewed set, not invented examples.
- [ ] Load results are measured at target concurrency; no capacity claims without logs.
- [ ] No fabricated college records are used; every real record shown has an authorized source and provenance. If no authorized records are available, the live-data demo is explicitly marked blocked.
- [ ] Screenshots/video show the current build and current deployment.
- [ ] Limitations and next steps are disclosed in the submission.
