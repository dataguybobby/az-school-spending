# ADE October 1 enrollment

Official Arizona Department of Education October 1 enrollment, loaded as a comparison beside the screened AP and voucher index. The raw ADE Excel workbooks are not in this repository. `pipeline/enrollment.py` loads the CSV extracts in this folder. Counts are the printed `Total` column. Nothing in this folder is ADM.

## Files

- `enrollment_october1_lea.csv` — official LEA-level October 1 totals, school years 2010-2011 through 2025-2026.
- `enrollment_october1_focus_leas.csv` — Chandler (4242), Higley (4248), Queen Creek (4245), Scottsdale (4240), and Paradise Valley (4241), including the 2010-2011 residence-pair rows ADE printed.
- `sources.json` — per-workbook year label, SHA-256, source URL, tabs, and data-quality notes.
- `index_leas.json` — the five spending-index sources and their ADE entity ids. Names are not guessed.

Listing page: https://www.azed.gov/accountability-research/data

## What a count is

This is a headcount of students enrolled on October 1. ADE's fiscal year N is school year (N-1)-N. Fiscal year 2026 is school year 2025-2026, the count taken on October 1, 2025.

An asterisk is ADE suppression (a group of 10 or fewer students, or complementary suppression). A blank Total stays blank. Both are stored as null with the printed reason. They are not filled, interpolated, or modeled. Rows are not summed to invent a total ADE did not print.

## Year match for a per-student figure

School year YYYY-(YYYY+1) pairs with spending dated July 1, YYYY through June 30, YYYY+1.

School year 2025-2026 pairs with spending dated 2025-07-01 through 2026-06-30. It does not pair with spending that starts on 2024-07-01. That date is the start of school year 2024-2025 and the start of this project's spending coverage window. The coverage window stays 2024-07-01. The year-match rule is only for the per-enrolled-student comparison.

A line with no date on the selected basis is not assigned a school year from the native fiscal-year label. One year's enrollment is not carried into another year.

The figure, when both sides exist, is a reported amount in this index per enrolled student. It is a screened AP or voucher extract divided by the October 1 headcount. It is not cost per pupil, not complete per-pupil spending, and not total district spending. Salaries are not in this extract. A partial packet is not a full school year.

## Comparability break

2017-2018 onward comes from the LEA by Grade tab (LEA of enrollment). Those years can be read as one series.

2011-2012 through 2016-2017 have no LEA tab. The district figures are district-of-residence subtotals ADE printed in the school tab. They can include resident students attending schools outside the LEA. They are not the same basis as 2017-2018 onward and are not shown as a continuous series with those later years.

2010-2011 has no single all-students LEA total. ADE printed one subtotal per attending LEA and district-of-residence pair. The row whose residence id matches the district's own entity id is only that pair. Other residence ids are kept as their own rows and are not added in.

## Focus districts

The five districts are matched on the entity ids above. Charter LEAs whose names contain Chandler, Queen Creek, Scottsdale, or a similar city are listed in `sources.json` under `unmatched_focus_candidates`. They are not part of these districts and are not added to these counts.

## Other notes kept from the workbooks

The LEA by Grade `Total` is the total used here. Other tabs can disagree; ADE has said totals may not match precisely across tabs because some student-characteristic fields were missing. Statewide totals that were blank or `*` stay null. The 2016-2017 statewide total is the number printed in that workbook. Small counts in the 2010-2011 through 2012-2013 files are kept as ADE published them. The 2025-2026 file prints small grade totals under a newer redaction rule.
