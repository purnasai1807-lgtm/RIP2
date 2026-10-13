# CampusRipple — Pitch Brief

## One-line pitch

CampusRipple helps colleges see the possible ripple effects of an operational decision before approving it, with explainable impact chains, evidence provenance, mitigation suggestions, and reviewable decision records.

## Problem

College operations span timetables, rooms, examinations, faculty availability, events, transport, facilities, and budgets. A change recorded in one place can create downstream conflicts elsewhere. Manual coordination can make those dependencies difficult to inspect consistently.

## Solution

A decision owner records the proposed change. CampusRipple creates a traceable impact chain, separates record-backed evidence from rule-based hypotheses, suggests mitigations, and lets users compare alternatives before the institution updates its authoritative systems.

## Differentiation

- **Explainability:** every impact carries a cause, severity, likelihood, mitigation, and source label.
- **Causal traceability:** impacts are organized into direct and downstream levels.
- **Evidence-aware:** saved college records can support findings without pretending a generic rule is verified data.
- **Decision governance:** ownership checks, coordinator/admin review, audit events, and CSV exports.
- **Institutional integration path:** a bounded read-only API adapter and validated CSV import path can be configured when authorized data access is granted.

## Current implementation boundary

CampusRipple is a functioning decision-support application with transparent rule-based analysis. It is not an empirically validated prediction model, does not replace the official college ERP/SIS, and does not automatically publish schedule changes. Official integration, stakeholder validation, and production acceptance depend on college authorization and real test evidence.

## Impact measurement plan

1. Recruit college operations stakeholders to define representative decisions and impact labels.
2. Label a review set independently, reconcile disagreements, and freeze a held-out acceptance set.
3. Measure precision, recall, F1, false positives, and missed impacts by domain and severity.
4. Track mitigations accepted, conflicts caught before approval, and time to review only after a pilot has reliable baseline measurements.
5. Publish the method, sample size, limitations, and date alongside all reported metrics.

## Closing

CampusRipple does not replace a decision-maker. It makes the consequences, evidence, and uncertainties behind a decision easier to inspect before a change becomes operational.
