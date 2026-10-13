# CampusRipple architecture (implemented boundaries)

```mermaid
flowchart TD
    U[Student / Faculty / Coordinator / Admin] --> UI[Responsive Flask templates + JS]
    UI --> R[Authenticated Flask routes]
    R --> AUTH[Authentication, role and ownership checks]
    R --> SVC[Scenario and college operations services]
    SVC --> DB[(SQLAlchemy database / PostgreSQL)]
    SVC --> EV[Evidence collector]
    EV --> DB
    SVC --> ENG[Transparent rule-based impact engine]
    ENG --> CHAIN[Direct and downstream impact chain]
    CHAIN --> REVIEW[Mitigation, alternative comparison and review]
    REVIEW --> AUDIT[Audit events and report export]
    EXT[Authorized college read-only API] -. configured integration only .-> ADAPTER[Timeout / retry / validation / provenance adapter]
    ADAPTER --> DB
    OPS[Release checks, migrations, backups, health endpoints] --> DB
```

## Trust boundaries

- Public registration cannot grant elevated roles; administrator provisioning is an operator action.
- Scenario access is restricted by ownership, with explicitly permitted coordinator/admin access where the route allows it.
- External API payloads are untrusted input and must pass validation before storage.
- Rule-based hypotheses are not official college facts. Only explicitly sourced application records count as record-backed evidence.
- Production secrets, real SMTP, HTTPS, live ERP/SIS credentials, restore drills, and performance evidence are deployment responsibilities, not bundled sample values.
