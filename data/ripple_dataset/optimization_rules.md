# Operating Rules and Evaluation Semantics

This document specifies what a valid plan must respect, not which algorithm to use.

## Hard feasibility rules
1. Room capacity, required features, opening hours, closures, setup/teardown, and room non-overlap.
2. All required services available throughout activity duration, unless an explicitly approved activity mode changes requirements.
3. Activity start within allowed time window and duration at least the minimum.
4. Hard dependency edges and minimum gaps.
5. Required qualified staff count, availability, breaks, and no simultaneous assignments.
6. Facility-specific qualification and safety requirements.
7. Engineering skill eligibility, work window, non-preemption, one job at a time, prerequisites, verification, parts stock, and restoration mappings.
8. No undocumented changes to activity modes, requirements, or cancellation policy.

## Objective order
Use a lexicographic or demonstrably equivalent weighted objective: (1) safety and hard feasibility, (2) minimize cancelled/undelivered activities weighted by priority, (3) minimize priority-weighted delay, (4) minimize relocations, (5) minimize soft-dependency penalties, (6) minimize engineering completion time and unnecessary resource use. Report objective weights and assumptions.

## Interpretation
A plan is feasible only if every hard constraint is verified. If no plan is found, distinguish proven infeasibility from search failure. Report insufficient data separately from both.
