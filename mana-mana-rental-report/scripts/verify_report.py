#!/usr/bin/env python3
"""Verify the Mana Mana rental report against its source statement PDFs.

Usage:
    python verify_report.py [--folder DIR] [--html index.html] [--quiet]

Checks three layers:
  1. every statement PDF is internally consistent (its own subtotals add up)
  2. the year-to-date figures derived from the PDFs reconcile
  3. index.html actually contains those figures, and its trend-line series match

Exit code 0 = all checks passed, 1 = at least one failure.

Run this after every update, before committing. It catches exactly the class of
bug that slipped through once: a year-to-date total that no longer matched the
per-month columns.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_statement import MO_KEYS, MONTH_NAMES, OPEX_KEYS, parse  # noqa: E402

LOAN = 2060.00
TOL = 0.02  # statements are rounded to 2dp, so allow a cent or two

ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
FULL = ["January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"]

DEFAULT_FOLDER = Path.home() / "Desktop" / "mana mana report" / "mana mana"

# trend-line series title -> (how to recompute its values, decimal places used in the HTML)
SERIES_MAP = {
    "Collected Revenue (100%)": (lambda m: m["collected_100"], 2),
    "Occupancy Rate": (lambda m: m["occupancy_rate"], 1),
    "Avg Room Rate": (lambda m: m["avg_room_rate"], 2),
    "Total Operating Expenses": (lambda m: m["total_opex"], 2),
    "Owner's Entitlement": (lambda m: m["entitlement"], 2),
    "Net Entitlement After Loan": (lambda m: m["entitlement"] - LOAN, 2),
}


class Report:
    def __init__(self, quiet=False):
        self.failures = []
        self.checks = 0
        self.quiet = quiet

    def check(self, ok, label, detail=""):
        self.checks += 1
        if not ok:
            self.failures.append(f"{label}{(' — ' + detail) if detail else ''}")
            print(f"  FAIL  {label}{(' — ' + detail) if detail else ''}")
        elif not self.quiet:
            print(f"  ok    {label}")

    def close(self, a, b):
        return abs(a - b) <= TOL


def money(v):
    return f"{v:,.2f}"


def load_months(folder):
    """Return the statement PDFs in month order, parsed."""
    found = []
    for p in folder.glob("*.pdf"):
        m = re.match(r"^(\d{2})_22mac_financial_report_(\w+)\.pdf$", p.name)
        if m:
            found.append((int(m.group(1)), p))
    found.sort()

    months = []
    for idx, path in found:
        raw = parse(path)
        f = raw["figures"]
        opex = {k: f.get(k, 0.0) for k in OPEX_KEYS}
        mo = {k: f[k] for k in MO_KEYS if f.get(k)}
        months.append({
            "idx": idx,
            "file": path.name,
            "label": raw["statement_month"],
            "statement_no": raw["statement_no"],
            "short_term_rental": f["Short Term Rental"],
            "credit_card": f.get("Credit Card / E-Payment", 0.0),
            "commission": f.get("Commission", 0.0),
            "direct_expenses": f["Total Direct Expenses"],
            "collected_100": f["Collected Revenue (100%)"],
            "gross_80": f["Gross Revenue (80%)"],
            "opex": opex,
            "total_opex": f["Total Operating Expenses"],
            "net_profit": f["Owner Net Profit"],
            "mo": mo,
            "mo_total": round(sum(mo.values()), 2),
            "entitlement": f["Owner's Entitlement"],
            "hosted_nights": raw["hosted_nights"],
            "available_nights": raw["available_nights"],
            "occupancy_rate": raw["occupancy_rate"],
            "avg_room_rate": raw["avg_room_rate"],
        })
    return months


def check_folder(folder, months, r):
    """Catch statements that are sitting there unprocessed.

    This is the check that matters most: a new statement still carrying Mana
    Mana's original filename is invisible to the rest of this script, so without
    it a stale report would sail through verification.
    """
    print("\n[0] Statement folder hygiene")

    convention = re.compile(r"^\d{2}_22mac_financial_report_\w+\.pdf$")
    stray = sorted(p.name for p in folder.glob("*.pdf") if not convention.match(p.name))
    r.check(not stray, "no unprocessed statement PDFs in the folder",
            f"rename these first: {'; '.join(stray)}")

    idxs = [m["idx"] for m in months]
    r.check(idxs == list(range(1, len(idxs) + 1)), "statement month numbers are contiguous from 01",
            f"found {idxs}")
    for m in months:
        expected = f"{m['idx']:02d}_22mac_financial_report_{MONTH_NAMES[m['idx'] - 1]}.pdf"
        r.check(m["file"] == expected, f"filename matches the month it contains ({m['file']})",
                f"expected {expected}")
        r.check((m["label"] or "").startswith(FULL[m["idx"] - 1]),
                f"statement {m['idx']:02d} really is {FULL[m['idx'] - 1]}",
                f"contents say '{m['label']}'")



def check_statements(months, r):
    print("\n[1] Each statement is internally consistent")
    for m in months:
        tag = f"{m['label']} ({m['file']})"
        r.check(r.close(m["credit_card"] + m["commission"], m["direct_expenses"]), f"{tag}: cc + commission = direct expenses",
                f"{money(m['credit_card'] + m['commission'])} vs {money(m['direct_expenses'])}")
        r.check(r.close(m["short_term_rental"] - m["direct_expenses"], m["collected_100"]), f"{tag}: rental - direct = collected 100%")
        r.check(r.close(sum(m["opex"].values()), m["total_opex"]), f"{tag}: operating expense lines = total",
                f"{money(sum(m['opex'].values()))} vs {money(m['total_opex'])}")
        r.check(r.close(m["gross_80"] - m["total_opex"], m["net_profit"]), f"{tag}: gross 80% - opex = net profit",
                f"{money(m['gross_80'] - m['total_opex'])} vs {money(m['net_profit'])}")
        r.check(r.close(m["net_profit"] - m["mo_total"], m["entitlement"]), f"{tag}: net - MO charges = entitlement",
                f"{money(m['net_profit'] - m['mo_total'])} vs {money(m['entitlement'])}")
        r.check(r.close(m["hosted_nights"] / m["available_nights"] * 100, m["occupancy_rate"]),
                f"{tag}: occupancy = hosted / available",
                f"{m['hosted_nights']}/{m['available_nights']}")


def totals(months):
    t = {
        "revenue": round(sum(m["short_term_rental"] for m in months), 2),
        "direct_expenses": round(sum(m["direct_expenses"] for m in months), 2),
        "collected_100": round(sum(m["collected_100"] for m in months), 2),
        "gross_80": round(sum(m["gross_80"] for m in months), 2),
        "opex": round(sum(m["total_opex"] for m in months), 2),
        "net_profit": round(sum(m["net_profit"] for m in months), 2),
        "mo_total": round(sum(m["mo_total"] for m in months), 2),
        "entitlement": round(sum(m["entitlement"] for m in months), 2),
        "hosted_nights": sum(m["hosted_nights"] for m in months),
    }
    t["net_after_loan"] = round(t["entitlement"] - LOAN * len(months), 2)
    t["loan_total"] = round(LOAN * len(months), 2)
    t["margin"] = round(t["entitlement"] / t["revenue"] * 100, 1)
    return t


def check_totals(months, t, r):
    n = len(months)
    print(f"\n[2] Year-to-date reconciliation ({n} months)")
    r.check(r.close(t["revenue"] - t["direct_expenses"], t["collected_100"]), "YTD: revenue - direct = collected 100%")
    r.check(r.close(t["collected_100"] * 0.8, t["gross_80"]),
            "YTD: gross 80% = collected 100% x 0.8",
            f"{money(t['collected_100'] * 0.8)} vs {money(t['gross_80'])}")
    r.check(r.close(t["gross_80"] - t["opex"], t["net_profit"]), "YTD: gross 80% - opex = net profit",
            f"{money(t['gross_80'] - t['opex'])} vs {money(t['net_profit'])}")
    r.check(r.close(t["net_profit"] - t["mo_total"], t["entitlement"]), "YTD: net - MO charges = entitlement",
            f"{money(t['net_profit'] - t['mo_total'])} vs {money(t['entitlement'])}")
    r.check(r.close(t["entitlement"] - t["loan_total"], t["net_after_loan"]),
            f"YTD: entitlement - {n} x {money(LOAN)} = net after loan")
    r.check(r.close(t["net_profit"] / n, round(t["net_profit"] / n, 2)), "YTD: monthly average divides evenly")


def check_html(months, t, html_path, r):
    n = len(months)
    html = html_path.read_text(encoding="utf-8")
    print(f"\n[3] index.html matches the statements ({html_path.name})")

    # structure
    r.check(html.count("<table") == html.count("</table>"), "HTML: <table> tags balanced",
            f"{html.count('<table')} open vs {html.count('</table>')} close")
    r.check(html.count("<div") == html.count("</div>"), "HTML: <div> tags balanced",
            f"{html.count('<div')} open vs {html.count('</div>')} close")

    # header / title month range
    first, last = months[0]["idx"] - 1, months[-1]["idx"] - 1
    subtitle = f"{FULL[first]} \u2013 {FULL[last]} 2026"
    title = f"{ABBR[first]}\u2013{ABBR[last]} 2026"
    r.check(subtitle in html, f"HTML: subtitle covers '{subtitle}'")
    r.check(title in html, f"HTML: title covers '{title}'")

    # every month's headline figures present
    for m in months:
        for key, label in (("short_term_rental", "revenue"),
                           ("net_profit", "net profit"),
                           ("entitlement", "entitlement")):
            r.check(money(m[key]) in html, f"HTML: {m['label']} {label} = {money(m[key])}")
        occ = m["hosted_nights"] / m["available_nights"] * 100
        r.check(f"{occ:.1f}%" in html, f"HTML: {m['label']} occupancy {occ:.1f}%")
        r.check(money(m["avg_room_rate"]) in html, f"HTML: {m['label']} avg room rate {money(m['avg_room_rate'])}")

    # year-to-date totals
    for key, label in (("revenue", "total revenue 100%"),
                       ("collected_100", "collected revenue 100%"),
                       ("gross_80", "gross revenue 80%"),
                       ("opex", "total operating expenses"),
                       ("net_profit", "total net profit"),
                       ("mo_total", "total MO charges"),
                       ("entitlement", "owner's entitlement"),
                       ("net_after_loan", "net entitlement after loan")):
        r.check(money(t[key]) in html, f"HTML: YTD {label} = {money(t[key])}")

    r.check(f"Total ({n} months)" in html, f"HTML: total row says 'Total ({n} months)'")
    r.check(money(t["revenue"] / n) in html, f"HTML: average revenue / month = {money(t['revenue'] / n)}")
    r.check(f"{money(LOAN)}" in html, f"HTML: loan instalment {money(LOAN)}")

    # month-over-month table should have n-1 delta columns
    mom = html.split("Month-over-Month Comparison", 1)
    if len(mom) > 1:
        r.check(mom[1].count("\u2192") >= (n - 1), f"HTML: MoM table has {n - 1} delta columns")

    # trend-line series
    months_arr = re.search(r"var months = \[([^\]]*)\]", html)
    r.check(bool(months_arr) and len(months_arr.group(1).split(",")) == n,
            f"HTML: trend-line months array has {n} entries")

    for sm in re.finditer(r"title:\s*['\"](.+?)['\"].*?values:\s*\[([^\]]*)\]", html):
        title_, raw_vals = sm.group(1), sm.group(2)
        if title_ not in SERIES_MAP:
            continue
        recompute, ndigits = SERIES_MAP[title_]
        vals = [float(v) for v in raw_vals.split(",") if v.strip()]
        expect = [round(recompute(m), ndigits) for m in months]
        r.check(len(vals) == n, f"HTML: series '{title_}' has {n} points", f"found {len(vals)}")
        if len(vals) == n:
            bad = [f"{ABBR[months[i]['idx'] - 1]} {vals[i]:.{ndigits}f}!={expect[i]:.{ndigits}f}"
                   for i in range(n) if abs(vals[i] - expect[i]) > TOL]
            r.check(not bad, f"HTML: series '{title_}' values match the statements", "; ".join(bad))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--folder", type=Path, default=DEFAULT_FOLDER,
                    help=f"folder holding the statement PDFs (default: {DEFAULT_FOLDER})")
    ap.add_argument("--html", type=Path, default=None,
                    help="report to check (default: <folder>/index.html)")
    ap.add_argument("--quiet", action="store_true", help="only print failures")
    args = ap.parse_args()

    folder = args.folder
    html_path = args.html or folder / "index.html"
    if not folder.is_dir():
        print(f"Folder not found: {folder}")
        return 1
    if not html_path.is_file():
        print(f"Report not found: {html_path}")
        return 1

    months = load_months(folder)
    if not months:
        print(f"No statement PDFs matching MM_22mac_financial_report_<month>.pdf in {folder}")
        return 1

    print(f"Statements found: {len(months)} "
          f"({months[0]['label']} .. {months[-1]['label']})")

    r = Report(quiet=args.quiet)
    check_folder(folder, months, r)
    check_statements(months, r)
    t = totals(months)
    check_totals(months, t, r)
    check_html(months, t, html_path, r)

    print("\n" + "=" * 68)
    if r.failures:
        print(f"FAILED - {len(r.failures)} of {r.checks} checks did not pass:")
        for f in r.failures:
            print(f"  - {f}")
        return 1
    print(f"PASSED - all {r.checks} checks OK")
    print(f"  YTD revenue {money(t['revenue'])} | net profit {money(t['net_profit'])} | "
          f"entitlement {money(t['entitlement'])} | after loan {money(t['net_after_loan'])} | "
          f"margin {t['margin']}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
