---
name: mana-mana-rental-report
description: Update the 22 Macalisterz (Mana Mana) rental income HTML report for unit 30-01 when a new monthly statement PDF arrives in the "mana mana" folder, then publish it to GitHub Pages. Use when the user says "update the rental income report", "update report", "new monthly reports are in the mana mana folder", "push to github", "mana mana", or otherwise asks to refresh, regenerate, verify or republish the Mana Mana / 22 Macalisterz rental income report from new statement PDFs.
agent_created: true
---

# Mana Mana Rental Income Report Updater

Refresh the single-page HTML rental income report for unit **30-01, 22 Macalisterz**
from Mana Mana's monthly statement PDFs, verify it against the sources, and push it live.

## Locations

| What | Where |
|------|-------|
| Input folder (statement PDFs) | `C:\Users\PC\Desktop\mana mana report\mana mana\` |
| Output report | `<input folder>\index.html` |
| Git repo | the `mana mana` folder itself — `origin` = https://github.com/systemdevelop2026/rental-income-report.git |
| Published at | https://systemdevelop2026.github.io/rental-income-report/ |
| Viewer password | `22mac` (client-side gate inside `index.html`) |

The output file is **always** `index.html` — never rename it, GitHub Pages depends on it.
Update the `<title>` and header subtitle to reflect the new month range.

## Trigger phrases

Any of these start an update:

- "update the rental income report" / "update report"
- "new monthly reports are in the mana mana folder"
- "push to github"

## Automatic triggering

A recurring automation named **"Mana Mana rental report — check for new statements"**
(id `21fd16d8-d648-44da-b606-8938be059889`) polls the folder **every day at 10:00** and runs
this entire workflow when a new statement has landed. Statements typically arrive between
07:30 and 10:00, so a 10:00 run catches them the same day.

It is a no-op when nothing new is present — it lists the PDFs, finds no unprocessed month and
stops without touching any file. To change the schedule, pause it or delete it, use the
automation tooling with that id rather than editing files.

There is no native "fire the moment a file is dropped" watcher — polling is the supported
mechanism. Do not build a background file-watcher process; it will not survive a restart.

## Workflow

### Step 1 — Find new statement PDFs

```bash
ls -la "C:/Users/PC/Desktop/mana mana report/mana mana/"*.pdf
```

A statement is **new** when its month is not yet reflected in `index.html`. A file still
carrying Mana Mana's original name (`22 3001MM26…` or `6X_22 3001MM26…`) has not been
processed. Cross-check against the "Processed months" table at the bottom of this file.

### Step 2 — Verify the month, then rename

Original names arrive as `22 3001MM26.pdf` or `6X_22 3001MM26_251215_XXXXX.pdf`, where `MM`
is the month, `26` the year 2026 and `3001` the unit code.

Rename to `MM_22mac_financial_report_<monthname>.pdf`, e.g. September 2026 becomes
`09_22mac_financial_report_september.pdf`.

**Confirm the month from the PDF contents before renaming — never trust the filename.**
Open the PDF and read `Statement Month` and `Billing Period`. Then rename and append the
mapping plus its rollback command to `PDF_RENAME_LOG.txt`.

Never overwrite an existing destination file — abort if it already exists.

> PDFs are covered by `.gitignore` (`*.pdf`), so renaming and adding statements never
> dirties the git repo. Only `index.html` and the `.txt` helpers are tracked.

### Step 3 — Extract the data

Run the bundled extractor on every statement. It reads the PDFs in place — there is no need
to copy them anywhere, and the `Read` tool cannot render these PDFs.

```bash
PY="C:/Users/PC/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe"
SKILL="C:/Users/PC/.workbuddy-ai/skills/mana-mana-rental-report"
cd "C:/Users/PC/Desktop/mana mana report/mana mana"

"$PY" "$SKILL/scripts/extract_statement.py" 09_22mac_financial_report_september.pdf
```

It prints JSON with the identity fields, every label/value pair on the statement's details
page, the hosted/available nights and the derived occupancy rate. New line items appear
automatically — the parser walks the label/value list rather than matching fixed names.

Each statement is 3 pages: page 1 identity, page 2 all figures, page 3 general information.

### Step 4 — Derive and sanity-check the month

| Field | How |
|-------|-----|
| `collected_revenue_100pct` | `total_collected_revenue − total_direct_expenses` |
| `gross_revenue_80pct` | use the figure **printed on the statement** (it is `collected 100% × 0.8`) |
| `owner_net_profit` | `gross 80% − total_operating_expenses` |
| `owners_entitlement` | `owner_net_profit − MO charges` (only the charges that appear that month) |
| `occupancy_rate` | `hosted_nights / available_nights × 100`, one decimal |

MO charges that may appear: Maintenance Fee, Sinking Fund, Assessment Fee, Quit Rent,
IWK Sewerage, Fire Insurance. Subtract only those actually listed for the month; absent
ones show as `—` in the report.

### Step 5 — Update `index.html`

**Keep the existing CSS exactly as-is** — bar alignment depends on it. Refresh:

1. **Header / `<title>`** — new month range
2. **KPI cards** — year-to-date totals and averages
3. **Revenue & Profit Trend** table — add the month's row, then refresh the
   `Total (n months)` and `Average / Month` rows
4. **Monthly Revenue Breakdown** — new column + updated Total
5. **Occupancy & Room Rate Trends** — one new bar in each sub-chart
6. **Monthly Operating Expenses** — new column + Total + Avg/Mo
7. **Net Profit & Owner's Entitlement** — new column, including the MO charge rows
8. **Net Profit After Bank Loan** — new column (loan = **RM 2,060.00**/month)
9. **Month-over-Month Comparison** — newest delta column
10. **Key Insights** — refresh the observations
11. **Footer** — generation date + statement range
12. **Trend-line JS** — append the new value to every `series[].values` array and add the
    month to the `months` array

**Bar height formula** (occupancy + room-rate sub-charts):

```
height_px = value / 5635 * 200      // Jan revenue RM 5,635 = 200px reference
```

Round to the nearest integer. The occupancy chart uses a 0–100% axis, the room-rate chart a
140–220 axis. The Revenue & Profit Trend section is a **table**, not a bar chart, despite the
`.bar` CSS still existing for the two sub-charts above.

### Step 6 — Verify before publishing

```bash
"$PY" "$SKILL/scripts/verify_report.py"
```

This is the gate. It checks 120+ conditions across three layers — each statement's own
subtotals, the year-to-date reconciliation, and whether `index.html` actually contains every
derived figure (including all six trend-line series). Exit code 0 means safe to publish.

Do not commit while it reports failures. It exists because a stale year-to-date total once
shipped unnoticed — the check for `gross 80% = collected 100% × 0.8` catches exactly that.

### Step 7 — Commit and push

Pushing is part of the standard update — do it automatically, do not wait for a separate request.

```bash
cd "C:/Users/PC/Desktop/mana mana report/mana mana"
git add -A
git commit -m "Add <Month> 2026 monthly report"
git push origin main
git ls-remote origin main                      # compare with: git rev-parse HEAD
git log origin/main..HEAD --oneline            # must print nothing
```

Then tell the user the new month is live at
https://systemdevelop2026.github.io/rental-income-report/

## Processed months — data reference (Jan–Aug 2026)

| Field | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug |
|-------|-----|-----|-----|-----|-----|-----|-----|-----|
| Short Term Rental | 5,635.34 | 5,397.84 | 5,261.58 | 4,671.22 | 4,822.54 | 4,883.32 | 5,628.29 | 5,824.60 |
| Credit Card / E-Payment | 266.80 | 1.72 | 3.37 | 3.65 | 3.02 | 1.67 | 3.86 | 3.95 |
| Commission | 233.32 | 385.42 | 356.94 | 403.34 | 400.64 | 368.25 | 576.40 | 627.15 |
| Total Direct Expenses | 500.12 | 387.14 | 360.31 | 406.99 | 403.66 | 369.92 | 580.26 | 631.10 |
| Collected Revenue (100%) | 5,135.22 | 5,010.70 | 4,901.27 | 4,264.23 | 4,418.88 | 4,513.40 | 5,048.03 | 5,193.50 |
| Gross Revenue (80%) | 4,108.18 | 4,008.56 | 3,921.02 | 3,411.38 | 3,535.10 | 3,610.72 | 4,038.42 | 4,154.80 |
| Electricity | 73.80 | 108.71 | 148.59 | 131.49 | 137.97 | 153.26 | 133.89 | 126.41 |
| Water | 29.58 | 31.51 | 37.86 | 20.32 | 31.74 | 31.59 | 27.19 | 0.00 |
| Internet | 0.00 | 0.00 | 0.00 | 0.00 | 0.48 | 0.00 | 0.00 | 0.00 |
| Repair & Maintenance | 0.00 | 0.00 | 1.42 | 0.55 | 4.36 | 4.29 | 1.57 | 4.00 |
| Room Cleaning | 368.91 | 453.29 | 602.96 | 425.49 | 417.45 | 434.52 | 439.36 | 437.87 |
| Room's Amenities | 43.30 | 45.00 | 30.00 | 0.00 | 42.35 | 43.49 | 45.00 | 41.17 |
| Total Operating Expenses | 515.59 | 638.51 | 820.83 | 577.85 | 634.35 | 667.15 | 647.01 | 609.45 |
| Owner Net Profit | 3,592.58 | 3,370.06 | 3,100.19 | 2,833.53 | 2,900.75 | 2,943.57 | 3,391.41 | 3,545.35 |
| MO Maintenance Fee | 243.20 | 121.60 | — | — | — | 121.60 | 121.60 | 121.60 |
| MO Sinking Fund | 24.32 | 12.16 | — | — | — | 12.16 | 12.16 | 12.16 |
| MO Assessment Fee | — | — | 11.78 | — | — | — | — | — |
| MO Quit Rent | — | — | 16.82 | — | — | — | — | — |
| IWK Sewerage Charges | — | — | — | 40.90 | — | 20.45 | — | — |
| MO Fire Insurance | — | — | — | — | 123.39 | — | — | — |
| Owner's Entitlement | 3,325.06 | 3,236.30 | 3,071.59 | 2,792.63 | 2,777.36 | 2,789.36 | 3,257.65 | 3,411.59 |
| Occupancy Rate | 82.1% | 93.0% | 80.8% | 80.8% | 80.8% | 90.5% | 96.3% | 93.6% |
| Avg Room Rate | 212.59 | 207.27 | 210.05 | 192.73 | 192.25 | 178.71 | 188.53 | 200.64 |
| Hosted nights | 891 | 1,064 | 1,027 | 921 | 952 | 1,023 | 1,015 | 987 |

YTD (Jan–Aug 2026): revenue RM 42,124.73 · collected 100% RM 38,485.23 · gross 80%
RM 30,788.18 · direct expenses RM 3,639.50 · OpEx RM 5,110.74 · owner net profit
RM 25,677.44 · MO charges RM 1,015.90 · owner's entitlement RM 24,661.54 · net after loan
RM 8,181.54 · margin 58.5%.

Fixed monthly bank loan instalment: **RM 2,060.00**.

> The "Gross Revenue (80%)" columns are `collected revenue (100%) × 0.8`, so the column total
> must equal `0.8 × 38,485.23 = 30,788.18`. An earlier version of the report carried a stale
> total of 29,120.64 that did not reconcile; it was corrected during the August 2026 update.

## Testing this skill without touching the live report

To rehearse an update safely, rebuild it in a sandbox and diff the result:

1. Make a throwaway folder. Copy in the statement PDFs, and set `index.html` to the
   *previous* month's version — `~/.openclaw/workspace/index.html.pre-aug.bak` is the
   Jan–Jul 2026 report and works well as a fixture.
2. Leave the newest statement under its original Mana Mana name, so the rename step is
   exercised too. `git init` the sandbox with **no remote** — the commit step is then
   testable and nothing can reach GitHub.
3. Confirm the gate refuses before the update: `verify_report.py` should fail on the
   unprocessed PDF and on every figure the stale report is missing.
4. Run Steps 2–5 against the sandbox, then run the verifier again — it must pass.
5. Diff the sandbox `index.html` against the live one. They should match except for the
   footer generation date. That is the strongest available check that the update is correct.

Verified 2026-09-25: a full rehearsal from the Jan–Jul fixture produced a file byte-for-byte
identical to the live Jan–Aug report apart from the generation date, and passed all 139 checks.
A current, up-to-date report passes 139 checks; the check count grows as months are added.

## Gotchas

- **Rename before processing.** Any file still named `22 3001MM26…` or `6X_22 3001MM26…`
  is unprocessed. Never overwrite an existing `MM_22mac_financial_report_<month>.pdf`.
- **Statement PDFs need PyMuPDF.** They use embedded subset fonts, so raw stream extraction
  returns garbage and the `Read` tool cannot render them. The bundled scripts use
  `pymupdf` from the managed venv at
  `C:\Users\PC\.workbuddy-ai\binaries\python\envs\default` (already installed). If that venv
  is missing: `python.exe -m pip install pymupdf`.
- **Preserve the CSS** in `index.html`; never rename `index.html`.
- **`TRIGGER_PHRASES.txt` is stale** (frozen at 25 July 2026). `HOW_TO_UPDATE_REPORT.txt` is
  the current user-facing note; update both when the workflow changes.
- **The "Total Hosted Trips" row actually holds hosted nights**, not trip count — that is
  what the statement's `x/y` figure means, and what occupancy is computed from.
- **Cosmetic:** the room-rate bars are drawn at roughly `rate × 0.9` px while their axis
  labels read 140–220, so the bars sit higher than the labels imply. Pre-existing; leave
  alone unless the user asks.
- **Git pushes run unattended.** `~/.gitconfig` clears the inherited `helper-selector` entry
  with an empty `helper =` and then points at Git Credential Manager via a space-free short
  path. Credentials for `systemdevelop2026` are in Windows Credential Manager. The path
  contains a version number (`v0.2.37.630`), so re-check after any QClaw/WorkBuddy upgrade.
- **Keep the copies in sync.** This skill exists as:
  1. the installed copy — `~/.workbuddy-ai/skills/mana-mana-rental-report/` (what triggers here)
  2. the QClaw copy — `~/.qclaw/skills/mana-mana-rental-report/` (only if QClaw is still used)
  3. the versioned copy — `<input folder>\mana-mana-rental-report\SKILL.md`, tracked in the
     same git repo as `index.html`

  Update all copies that exist whenever the workflow changes, and commit the versioned copy
  together with the report.
