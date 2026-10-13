# Activity priority CSV upload

Open **Activity priority** in the authenticated CampusRipple navigation and upload a UTF-8 `.csv` file using the campus activity schema. The required headers are `activity_id`, `activity_name`, `priority`, and `priority_weight`. The other columns in the supplied `activities.csv` schema are preserved in the source file and in the scored export.

Accepted `priority` values (case-insensitive): `critical`, `high`, `medium`, `low`. `priority_weight` must be a finite, non-negative number. Activity IDs must be unique. Files are limited to 1 MB and 2,000 rows. CSV quoting, commas, and multiline fields are handled by Python's CSV parser. A malformed or invalid upload does not replace the last accepted source file.

## Score

- Priority tier: critical = 100, high = 75, medium = 50, low = 25.
- Weight score: `priority_weight / maximum priority_weight in the uploaded file * 100` (0 when all weights are zero).
- Final score: `round(0.6 * priority tier + 0.4 * weight score)`.
- Classification: High for 70–100, Medium for 40–69, Low for 0–39.

This is a relative prioritization aid for the uploaded file, not a probability or safety assessment. The maximum weight is computed from each upload, so scores may change if a new file contains a larger maximum weight.

After successful scoring, the page shows a row-level table and summary counts. **Download scored CSV** downloads all original columns plus `priority_score` and `priority_classification`. The uploaded source and scored result are saved under the app's instance directory, not written by the browser to a server path.
