# CampusRipple — Hackathon Judge Demo Runbook

## Positioning

**CampusRipple is a college decision-impact workspace that helps a decision owner inspect potential downstream consequences before changing a timetable, exam, facility booking, event, transport plan, or budget.** It combines scenario authoring, transparent rule-based impact chains, available local-record evidence, alternative comparison, review workflow, and traceable exports.

Do not describe rule-generated impacts as certain predictions. State which observations are database-backed and which are hypotheses.

## 4-minute live demo

1. **Problem (30 seconds):** Explain how one schedule change can affect rooms, faculty, labs, transport, and assessments across separate spreadsheets and conversations.
2. **Create a decision (45 seconds):** Sign in with an approved, real institutional account and use only an authorized real decision with traceable source records. If these are unavailable, do not fabricate a walkthrough; present the product architecture and mark live workflow validation as blocked.
3. **Run analysis (60 seconds):** Show level 1 direct effects and level 2/3 downstream effects. Open a result and point out its cause, severity, likelihood, mitigation, and source label.
4. **Evidence vs hypothesis (30 seconds):** Show a finding based on a saved college record separately from a generic rule-based hypothesis. If the demo database contains no matching record, say so—do not manufacture evidence.
5. **What-if comparison (45 seconds):** Compare the original proposal with an alternative and discuss the difference in severity counts and mitigation workload.
6. **Governance (30 seconds):** Show private scenario access, coordinator/admin review, audit trail, and CSV export.
7. **Close (20 seconds):** Explain next integrations and how stakeholder feedback will validate the rule set.

## Account and data integrity (no fake demo data)

- Do not seed or invent student, staff, timetable, examination, or other college records for a presentation. The `seed-demo-data` command is intentionally disabled.
- Use only accounts and records authorized by ACEEC through the approved workflow. Never hard-code production credentials.
- Minimize personal data and use it only with written authorization, access controls, and an approved retention policy. If authorization or records are unavailable, show the UI/architecture without inventing populated records and clearly state that live-data validation is blocked.
- Do not claim ACEEC ERP/SIS connectivity unless the authorized integration ran successfully and reconciliation evidence is available.

## Judge questions to prepare for

- **How is an impact generated?** Transparent domain rules in `app/engine.py`, with source labels and causal links.
- **What is verified?** Only findings tied to an identified application record; generic rules remain hypotheses.
- **How do you prevent false confidence?** Explicit provenance, reviewer feedback, stakeholder-labeled validation, and no performance/accuracy claims without measurements.
- **How is data protected?** Password hashing, role checks, scenario ownership, CSRF protection, input validation, audit events, and deployment secrets kept outside source control.
- **What happens if the official API is down?** The adapter applies bounded timeout/retry/validation behavior; freshness and sync history must be checked, and stale data must not be represented as current.
- **What is not yet proven?** Live ERP/SIS reconciliation, real SMTP delivery, PostgreSQL restore drills, stakeholder accuracy, and measured staging load capacity until evidence is collected.

## Evidence to capture before submission

- A short screen recording of the full workflow.
- Screenshots of scenario creation, a complete impact chain, what-if comparison, source labels, review workflow, and exported report.
- Passing local test output and PostgreSQL integration logs from a real run.
- A one-page limitations/data-governance statement.
- Measured performance results only from a controlled staging run.
