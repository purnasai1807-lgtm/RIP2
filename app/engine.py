"""College-focused, transparent rule-based impact analysis. Review all outputs against real college data."""

RULE_VERSION = 'college-rules-2026.10.13-phase6.1'

RULES = {
    'Timetable & classrooms': [
        (1, 'Classroom and faculty conflict', 'Moving a lecture can overlap another class or the faculty member’s assigned period.', 'Room and faculty schedules are shared, time-dependent resources.', 'High', 'High', 'Check the master timetable and confirm both room and faculty availability.'),
        (2, 'Laboratory or tutorial disruption', 'A timetable conflict may push a dependent lab, tutorial, or practical session into another slot.', 'Practical sessions often depend on lecture completion, room availability, and faculty coverage.', 'High', 'Medium', 'Move the dependent session to a verified open slot and notify the lab in-charge.'),
        (2, 'Student transport and attendance', 'A later finish or changed period may conflict with bus departure times or other classes.', 'Students plan transport and class attendance around the published timetable.', 'Medium', 'Medium', 'Check bus timings and class clashes before publishing the revised timetable.'),
        (3, 'Syllabus and assessment delay', 'Lost practical time or missed classes may reduce time available for syllabus completion and revision.', 'Syllabus progress depends on the availability of teaching and practical periods.', 'High', 'Medium', 'Publish a revised academic plan and add a make-up period if required.'),
    ],
    'Exams & academics': [
        (1, 'Exam timetable clash', 'Changing an exam date or time can overlap another subject exam or scheduled academic activity.', 'Students, halls, invigilators, and subjects may share the same schedule.', 'High', 'High', 'Validate the full exam calendar before confirming the change.'),
        (2, 'Hall and invigilator shortage', 'A changed exam slot can create simultaneous demand for rooms and invigilators.', 'Exam capacity depends on available halls, seating limits, and assigned staff.', 'High', 'Medium', 'Reserve suitable halls and assign invigilators before publishing the timetable.'),
        (2, 'Student preparation and travel impact', 'Students may have less preparation time or face transport and accommodation issues.', 'Preparation windows and travel arrangements depend on confirmed exam dates.', 'Medium', 'Medium', 'Give advance notice and check minimum gaps between papers.'),
        (3, 'Evaluation and result delay', 'Rescheduling can compress evaluation timelines and delay result processing.', 'Evaluation depends on scripts arriving after exams and staff having sufficient time.', 'Medium', 'Medium', 'Update the evaluation calendar and assign realistic completion dates.'),
    ],
    'Campus facilities': [
        (1, 'Facility capacity conflict', 'Changing a room, lab, or facility booking may overlap another approved use.', 'Facilities have limited capacity and scheduled maintenance or usage windows.', 'High', 'High', 'Check the booking register and capacity limits before approval.'),
        (2, 'Practical or service interruption', 'An unavailable facility can delay labs, library services, workshops, or student activities.', 'These activities depend on access to the required space and equipment.', 'High', 'Medium', 'Arrange an alternate room or equipment and inform the responsible staff.'),
        (2, 'Maintenance and operating cost', 'A rushed change may require overtime, urgent setup, or additional equipment movement.', 'Unplanned work uses staff time and operating resources.', 'Medium', 'Medium', 'Compare the cost of a temporary alternative with rescheduling.'),
        (3, 'Learning experience impact', 'Repeated interruptions can reduce practical learning time and student satisfaction.', 'Learning outcomes depend on reliable access to facilities and equipment.', 'Medium', 'Medium', 'Track missed sessions and schedule recovery time.'),
    ],
    'College events & clubs': [
        (1, 'Venue and schedule conflict', 'Changing an event date or time may overlap classes, exams, or another campus event.', 'Campus venues and student availability are shared across activities.', 'High', 'High', 'Check the academic calendar and event booking register.'),
        (2, 'Volunteer and equipment conflict', 'A schedule clash can make volunteers, sound systems, projectors, or other equipment unavailable.', 'Event delivery depends on staff, volunteers, and equipment being available together.', 'Medium', 'Medium', 'Confirm owners and equipment reservations against the revised schedule.'),
        (2, 'Participation and transport reduction', 'Students may be unable to attend due to classes, buses, or conflicting commitments.', 'Participation depends on accessible timing and clear communication.', 'Medium', 'Medium', 'Survey key participants and communicate the change through official channels.'),
        (3, 'Budget and reputation impact', 'Low attendance or last-minute changes can waste spending and reduce confidence in future events.', 'Event costs and stakeholder expectations are set around the approved plan.', 'Medium', 'Medium', 'Reforecast the budget and publish one confirmed event notice.'),
    ],
    'Transport & attendance': [
        (1, 'Route or departure mismatch', 'Changing college timings can leave bus departure times or route capacity out of sync.', 'Transport schedules are coordinated with class start and finish times.', 'High', 'High', 'Compare revised class timings with each route and confirm capacity with transport staff.'),
        (2, 'Late arrival or early departure', 'A mismatch can make students arrive late or leave before scheduled activities end.', 'Attendance depends partly on transport being available at the required time.', 'Medium', 'Medium', 'Adjust departures where feasible and communicate confirmed arrangements.'),
        (2, 'Crowding and supervision pressure', 'Concentrated arrival or departure times can increase crowding and staff workload.', 'Transport and campus entry capacity are limited during peak periods.', 'Medium', 'Medium', 'Stagger movements or add supervision at peak times.'),
        (3, 'Attendance and learning impact', 'Repeated transport problems may lead to missed lessons or practical sessions.', 'Learning participation depends on reaching campus and activities on time.', 'High', 'Medium', 'Track affected periods and provide a recovery plan for missed academic work.'),
    ],
    'Budget & procurement': [
        (1, 'Budget allocation conflict', 'Changing a purchase, quantity, or budget may reduce funds available for another department need.', 'College budgets are finite and often allocated across departments or activities.', 'High', 'Medium', 'Check the approved budget and obtain the required finance approval.'),
        (2, 'Procurement or delivery delay', 'A revised quantity or specification may require a new quote, approval, or delivery date.', 'Purchasing depends on supplier lead times and approval workflows.', 'Medium', 'Medium', 'Confirm supplier availability and approval steps before committing.'),
        (2, 'Teaching activity dependency', 'Missing equipment or supplies can delay labs, workshops, or scheduled activities.', 'Practical activities depend on required materials being available on time.', 'High', 'Medium', 'Prioritize essential academic requirements and arrange a temporary alternative.'),
        (3, 'Cost overrun or schedule slippage', 'Late procurement may create urgent purchases or force activities to be rescheduled.', 'Recovery actions often cost more or consume time from the academic calendar.', 'Medium', 'Medium', 'Compare alternatives, record the decision, and monitor delivery milestones.'),
    ],
    'General college decision': [
        (1, 'Immediate resource or schedule conflict', 'The proposed change may conflict with an existing college commitment.', 'College activities share rooms, staff, equipment, time, and budget.', 'Medium', 'Medium', 'Check the relevant timetable, booking record, and resource owner.'),
        (2, 'Dependent activity delay', 'A conflict can delay a class, lab, event, approval, or service that depends on the changed activity.', 'Downstream work cannot proceed until its prerequisite is ready.', 'Medium', 'Medium', 'Re-sequence dependent work or reserve a verified backup resource.'),
        (2, 'Extra workload or cost', 'Resolving the disruption may require extra staff time, equipment, or re-planning.', 'Recovery actions consume limited staff time and operating resources.', 'Medium', 'Medium', 'Compare the recovery cost with a lower-impact alternative.'),
        (3, 'Student and staff experience', 'Repeated disruption can affect student participation, staff workload, and confidence in college planning.', 'People depend on consistent schedules and timely communication.', 'Medium', 'Medium', 'Assign an owner, communicate the final plan, and review the outcome.'),
    ],
}

# Compatibility aliases for existing records created before the college-specific update.
RULES['Education'] = RULES['Timetable & classrooms']
RULES['General'] = RULES['General college decision']
RULES['Supply chain'] = RULES['Budget & procurement']
RULES['Healthcare'] = RULES['Campus facilities']
RULES['Software / IT'] = RULES['Campus facilities']


def analyze(domain, variable, current_value, proposed_value, context='', evidence=None):
    """Build a traceable impact chain.

    Domain rules are explicitly marked as hypotheses, not as facts about this college.
    Database evidence is added separately by the route layer. Every downstream rule is
    linked to the closest prior impact level so the UI can show its causal parent.
    """
    rules = RULES.get(domain, RULES['General college decision'])
    impacts = []
    change_text = f"{variable}: {current_value} → {proposed_value}"
    activities_by_level = {1: [], 2: [], 3: []}
    level_counts = {1: 0, 2: 0, 3: 0}
    for level, activity, description, cause, severity, likelihood, mitigation in rules:
        # Link each downstream rule to a prior-level impact deterministically. Cycling
        # across parents avoids incorrectly making every branch depend on the last item.
        if level == 1:
            parent_activity = 'Proposed change'
        else:
            possible_parents = activities_by_level.get(level - 1, [])
            if possible_parents:
                parent_activity = possible_parents[level_counts[level] % len(possible_parents)]
            else:
                parent_activity = 'Proposed change'
        if level == 1:
            cause_text = f"The proposed change ({change_text}) could affect this activity. {cause}"
        else:
            cause_text = f"Potential causal path: {parent_activity} → {activity}. This is a rule-based dependency hypothesis, not a confirmed event. {cause}"
        if context.strip():
            cause_text += f" Context supplied by the user: {context.strip()[:350]}"
        impacts.append({'level': level, 'activity': activity, 'description': description,
                        'cause': cause_text, 'severity': severity, 'likelihood': likelihood,
                        'mitigation': mitigation, 'source': 'rule-based hypothesis; verify against college records',
                        'parent_activity': parent_activity})
        activities_by_level.setdefault(level, []).append(activity)
        level_counts[level] = level_counts.get(level, 0) + 1
    for item in (evidence or []):
        # Evidence is a separate, record-backed input. Be defensive about malformed
        # levels and never allow an arbitrary parent label to create a false causal edge.
        try:
            level = max(1, min(3, int(item.get('level', 1))))
        except (TypeError, ValueError, OverflowError):
            level = 1
        possible_parents = activities_by_level.get(level - 1, []) if level > 1 else []
        requested_parent = str(item.get('parent_activity') or '').strip()
        if level == 1:
            parent_activity = 'Proposed change'
        elif requested_parent in possible_parents:
            parent_activity = requested_parent
        elif possible_parents:
            parent_activity = possible_parents[level_counts.get(level, 0) % len(possible_parents)]
        else:
            parent_activity = 'Proposed change'
        activity = str(item.get('activity') or 'Unspecified evidence impact').strip()[:140]
        description = str(item.get('description') or 'Evidence was recorded; review the linked source before acting.')
        cause = str(item.get('cause') or 'Cause not supplied; verify the linked source before acting.')
        mitigation = str(item.get('mitigation') or 'Review the source record and confirm an appropriate mitigation with the responsible owner.')
        impacts.append({
            'level': level,
            'activity': activity,
            'description': description,
            'cause': cause,
            'severity': item.get('severity', 'Medium') if item.get('severity') in {'Low', 'Medium', 'High', 'Critical'} else 'Medium',
            'likelihood': item.get('likelihood', 'Medium') if item.get('likelihood') in {'Low', 'Medium', 'High'} else 'Medium',
            'mitigation': mitigation,
            'source': item.get('source', 'college database evidence'),
            'parent_activity': parent_activity,
            'evidence_ref': item.get('evidence_ref'),
        })
        activities_by_level.setdefault(level, []).append(activity)
        level_counts[level] = level_counts.get(level, 0) + 1
    impacts.sort(key=lambda item: (item['level'], item['activity']))
    return impacts
