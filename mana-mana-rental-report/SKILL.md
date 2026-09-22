---
name: mana-mana-rental-report
description: Update the 22 Macalisterz (Mana Mana) rental income HTML report when a new monthly financial statement PDF arrives in the "mana mana" folder. Use when the user says "update the rental income report", "new monthly reports are in the mana mana folder", "update report", or "push to github" for this folder, or otherwise asks to refresh the Mana Mana rental report from new PDFs.
---

# Mana Mana Rental Income Report Updater

Refresh the single-page HTML rental income report for unit **30-01, 22 Macalisterz**
by extracting data from Mana Mana's monthly statement PDFs.

## Locations (Windows, current machine)

- **Input folder (PDFs)**: `C:\Users\PC\Desktop\mana mana report\mana mana\`
- **Output file**: `C:\Users\PC\Desktop\mana mana report\mana mana\index.html`
- **Git repo**: the `mana mana` folder itself (`origin` = https://github.com/systemdevelop2026/rental-income-report.git)
- **GitHub Pages**: https://systemdevelop2026.github.io/rental-income-report/
- **Viewer password**: `22mac`

> The output file is always `index.html` (never rename it) so GitHub Pages keeps working.
> Update the `<title>` tag in the HTML to reflect the new month range.

## PDF naming convention

Statement PDFs are renamed from Mana Mana's original filenames to a clean,
month-ordered convention:

```
01_22mac_financial_report_january.pdf
02_22mac_financial_report_february.pdf
03_22mac_financial_report_march.pdf
04_22mac_financial_report_april.pdf
05_22mac_financial_report_may.pdf
06_22mac_financial_report_june.pdf
07_22mac_financial_report_july.pdf
```

Pattern: `MM_22mac_financial_report_<monthname>.pdf` where `MM` is the zero-padded
month number (01–12) and `<monthname>` is the lowercase English month (e.g. `august`).

**Original Mana Mana filenames** arrive in one of two forms:

- `22 3001MM26.pdf` — e.g. `22 30010126.pdf`
- `6X_22 3001MM26_251215_XXXXX.pdf` — e.g. `6X_22 30010726_251215_KRX5E.pdf`

In both, `MM` is the month, `26` is the year 2026, and `3001` is the unit code.
So rename on arrival before processing. A rename log is written to
`PDF_RENAME_LOG.txt` in the same folder; it also contains the exact rollback commands.

## Trigger phrases

Any of these should start an update:

- "update the rental income report"
- "update report"
- "new monthly reports are in the mana mana folder"
- "push to github" (do the update first, then commit + push)

## Workflow

### Step 1 — Find new PDFs

```powershell
Get-ChildItem -LiteralPath 'C:\Users\PC\Desktop\mana mana report\mana mana' -Filter '*.pdf' |
  Select-Object Name, LastWriteTime
```

A PDF is "new" when its month is not already reflected in `index.html`. Any file
still carrying an original Mana Mana name (`22 3001MM26…` or `6X_22 3001MM26…`)
has not been processed yet and needs renaming.

### Step 2 — Rename new PDFs to the convention

Map the month digits to the target name, verifying the month against the PDF
contents first (the statement states its month and billing period explicitly).
Never overwrite: abort if a destination already exists.

```powershell
$dir = 'C:\Users\PC\Desktop\mana mana report\mana mana'

# MM -> month name
$months = @{ '01'='january'; '02'='february'; '03'='march'; '04'='april';
             '05'='may'; '06'='june'; '07'='july'; '08'='august';
             '09'='september'; '10'='october'; '11'='november'; '12'='december' }

Get-ChildItem -LiteralPath $dir -Filter '*.pdf' |
  Where-Object { $_.Name -match '3001(\d\d)26' } |
  ForEach-Object {
    $mm  = $Matches[1]
    $dst = '{0}_22mac_financial_report_{1}.pdf' -f $mm, $months[$mm]
    $out = Join-Path $dir $dst
    if (Test-Path -LiteralPath $out) { Write-Host "SKIP (exists): $dst"; return }
    Rename-Item -LiteralPath $_.FullName -NewName $dst
    Write-Host "RENAMED $($_.Name) -> $dst"
  }
```

### Step 3 — Copy new PDFs into the workspace

The `pdf` tool can only read files under the workspace, so copy them first:

```powershell
$src  = 'C:\Users\PC\Desktop\mana mana report\mana mana'
$dest = "$env:USERPROFILE\.openclaw\workspace\mana_mana_pdfs"
New-Item -ItemType Directory -Path $dest -Force | Out-Null
Get-ChildItem -LiteralPath $src -Filter '*.pdf' | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $dest $_.Name) -Force
}
```

Then read each new PDF with the `pdf` tool.

### Step 4 — Extract fields from each statement

**Identity**
- `statement_month` (e.g. "July 2026"), `statement_no` (e.g. "22 30010726")
- `billing_period` (e.g. "01/07/2026 - 31/07/2026")
- `unit` = 30-01
- `owner_name` = NG YONG YONG & NG KIM HOOI & NG CHENG CHENG & NG MOOI LENG

**Revenue**
- `short_term_rental`, `total_collected_revenue`
- hosted trips as `x/y` (booked / available nights), `avg_room_rate`

**Direct expenses**
- `credit_card_epayment`, `commission`, `total_direct_expenses`

**Derived**
- `collected_revenue_100pct` = total_collected_revenue − total_direct_expenses
- `gross_revenue_80pct` = use the exact figure printed on the statement
  (it is close to, but not always exactly, collected_revenue_100pct × 0.8)

**Operating expenses**
- electricity, water, internet, str_fees, sales_marketing, repair_maintenance,
  room_cleaning, laundry, account_admin, rooms_amenities, others
- `total_operating_expenses`

**Final**
- `owner_net_profit`
- MO charges — only include the ones that actually appear that month:
  Maintenance Fee, Sinking Fund, Assessment Fee, Quit Rent, IWK Sewerage, Fire Insurance
- `owners_entitlement` (final payout)

**Performance**
- `hosted_trips`, `total_nights`, `occupancy_rate = hosted_trips / total_nights × 100`

### Step 5 — Update `index.html`

Sections to refresh (keep the existing CSS exactly as-is — it is tuned for bar alignment):

1. **Header** — month range
2. **KPI cards** — YTD totals / averages
3. **Revenue & Profit Trend table** — add the new month's row (Total Revenue 100%,
   Owner Net Profit, Owner's Entitlement, Profit Margin), then refresh the
   **Total (n months)** and **Average / Month** rows
4. **Monthly Revenue Breakdown table** — new column + updated Total
5. **Occupancy & Room Rate Trends** — add a bar to each sub-chart
6. **Monthly Operating Expenses table** — new column
7. **Net Profit & Owner's Entitlement table** — new column
8. **Net Profit After Bank Loan** table — new column (loan = RM 2,060/month)
9. **Month-over-Month Comparison** — add newest delta row
10. **Key Insights** — refresh observations
11. **Footer** — generation date + statement range
12. **Trend-line JS** — append the new value to every `series[].values` array
    and define a darker colour for the new month (`months` array + `series` arrays)

**Bar height formula** (occupancy + room-rate sub-charts):

```
height_px = value / 5635 * 200      // Jan revenue RM 5,635 = 200px reference
```

Round to the nearest integer. Occupancy chart uses a 0–100% axis and the room-rate
chart a 140–220 axis; scale each accordingly.

> The Revenue & Profit Trend section is a **table** (one row per month), not a bar
> chart — despite the `.bar` CSS still existing for the occupancy/room-rate charts.

### Step 6 — Verify, then publish (commit + push)

1. Open `index.html` (or re-read it) and confirm the new column/bars render and totals add up
   (column totals vs KPI cards, `Gross 80% − OpEx = Owner Net Profit`, `Loan = RM 2,060 × months`).
2. Commit and push as the **final step of every update**. Pushing to GitHub is part of the
   standard update workflow — do it automatically, do not wait for a separate request:

```powershell
Set-Location 'C:\Users\PC\Desktop\mana mana report\mana mana'
git add -A
git commit -m "Add <Month> 2026 monthly report"
git push origin main
```

3. Confirm the push landed (remote HEAD must equal local HEAD, no unpushed commits):

```powershell
git ls-remote origin main          # compare with: git rev-parse HEAD
git log origin/main..HEAD --oneline  # must print nothing
```

> If `git push` blocks on an interactive GitHub login (Git Credential Manager), surface it
> to the user: they must sign in once in the browser window that GCM opens; the push then
> completes automatically.
>
> **This machine is already configured for unattended pushes** (as of 2026-09-22):
> `~/.gitconfig` sets `credential.helper` to the QClaw-bundled Git Credential Manager via
> its short path `C:/PROGRA~1/QClaw/v0.2.37.630/resources/git/mingw64/bin/git-credential-manager.exe`,
> preceded by an empty `helper =` to clear the QClaw system-config `helper-selector` entry
> (which otherwise pops the "Select a credential helper" dialog on every push). A GitHub
> credential for user `systemdevelop2026` is stored in Windows Credential Manager
> (`cmdkey target=git:https://github.com`), and `git credential fill` returns it
> non-interactively. So `git push origin main` should now complete with no dialog.
> Do NOT re-add `credential.helper = manager` — the bare `manager` name resolves to the
> QClaw helper-selector, and paths containing spaces break the shell form.

## Data reference — processed months (Jan–Aug 2026)

| Field | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug |
|-------|-----|-----|-----|-----|-----|-----|-----|-----|
| Short Term Rental | 5,635.34 | 5,397.84 | 5,261.58 | 4,671.22 | 4,822.54 | 4,883.32 | 5,628.29 | 5,824.60 |
| Credit Card/E-Payment | 266.80 | 1.72 | 3.37 | 3.65 | 3.02 | 1.67 | 3.86 | 3.95 |
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
| IWK Sewerage | — | — | — | 40.90 | — | 20.45 | — | — |
| MO Fire Insurance | — | — | — | — | 123.39 | — | — | — |
| Owner's Entitlement | 3,325.06 | 3,236.30 | 3,071.59 | 2,792.63 | 2,777.36 | 2,789.36 | 3,257.65 | 3,411.59 |
| Occupancy Rate | 82.1% | 93.0% | 80.8% | 80.8% | 80.8% | 90.5% | 96.3% | 93.6% |
| Avg Room Rate | 212.59 | 207.27 | 210.05 | 192.73 | 192.25 | 178.71 | 188.53 | 200.64 |
| Hosted Trips | 891 | 1,064 | 1,027 | 921 | 952 | 1,023 | 1,015 | 987 |

YTD (Jan–Aug 2026): collected revenue RM 42,124.73 · collected 100% RM 38,485.23 ·
gross 80% RM 30,788.18 · OpEx RM 5,110.74 · owner net profit RM 25,677.44 ·
owner's entitlement RM 24,661.54 · net after loan RM 8,181.54 · margin 58.5%.

> Note: the report's "Gross Revenue (80%)" columns are `collected revenue (100%) × 0.8`.
> The column total must therefore equal `0.8 × 38,485.23 = 30,788.18` and
> `Gross 80% − OpEx = Owner Net Profit` must hold. (The pre-Aug 2026 report had a
> stale gross-80% total of 29,120.64 that did not reconcile; it was corrected to
> 30,788.18 during the August update.)

Fixed monthly bank loan instalment: **RM 2,060.00**.

## Notes & gotchas

- Run the rename step **before** processing: any file still named
  `22 3001MM26…` or `6X_22 3001MM26…` is unprocessed. Never overwrite an
  existing `MM_22mac_financial_report_<month>.pdf`.
- `PDF_RENAME_LOG.txt` in the `mana mana` folder records every rename and the
  exact rollback commands.
- Statement PDFs are covered by `.gitignore` (`*.pdf`), so renaming and adding
  PDFs never affects the git repo — only `index.html` and the `.txt` helpers are tracked.
- The `pdf` tool only reads under the workspace — always copy PDFs to
  `~/.openclaw/workspace/mana_mana_pdfs` first.
- Preserve the existing CSS; bar alignment depends on it.
- Do not rename `index.html`.
- Keep both copies of this skill in sync: the installed one at
  `~/.qclaw/skills/mana-mana-rental-report/SKILL.md` and the versioned copy at
  `C:\Users\PC\Desktop\mana mana report\mana mana\mana-mana-rental-report\SKILL.md`
  (tracked in the same git repo as `index.html`).
