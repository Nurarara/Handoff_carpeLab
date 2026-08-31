#!/usr/bin/env python3
"""
Notion -> Attio handoff, dry run.

Reads the Notion CSV export, applies the matching rules, and writes
import-ready files plus a review queue.

No dependencies. Nothing is sent anywhere.

    python3 handoff.py notion-qualified-accounts-w34.csv
"""

import argparse
import csv
import os
import re
import sys
from collections import OrderedDict

# Canonical employee bands. Notion sends these with two different dashes,
# which Attio would store as two separate select options.
BANDS = {
    "1-10": "1-10", "11-50": "11-50", "51-200": "51-200",
    "201-500": "201-500", "501-1000": "501-1000", "1001+": "1001+",
}


def domain_of(url):
    """Website -> bare domain. Strips scheme, www, path, query, trailing slash."""
    if not url:
        return ""
    s = url.strip().lower()
    s = re.sub(r"^[a-z][a-z0-9+.-]*://", "", s)   # scheme
    s = s.split("/")[0].split("?")[0].split("#")[0]  # path, query, fragment
    s = re.sub(r"^www\.", "", s)                   # leading www only
    s = s.split(":")[0]                            # port
    return s.strip(". ")


def band_of(raw):
    """Employee range -> canonical band. Handles en dash, em dash, spaces."""
    if not raw:
        return ""
    s = re.sub(r"[\u2010-\u2015\u2212]", "-", raw)  # all dash variants -> hyphen
    s = re.sub(r"\s+", "", s)
    return BANDS.get(s, s)


def split_name(full):
    """Person name -> (first, last). Last token is the surname."""
    parts = (full or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]), parts[-1]


def linkedin_of(url):
    return (url or "").strip().lower().rstrip("/")


def load(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def plan(rows):
    """Return (people, companies, held). Companies keyed by domain."""
    people, held = [], []
    companies = OrderedDict()

    for row in rows:
        get = lambda k: (row.get(k) or "").strip()

        source_id = get("Source ID")
        account = get("Account")
        website = get("Website")
        email = get("Work email").lower()
        linkedin = linkedin_of(get("LinkedIn"))
        domain = domain_of(website)
        band = band_of(get("Employees"))
        first, last = split_name(get("Contact"))

        notes, action = [], "create"

        if get("CRM company ID"):
            held.append({
                "Source ID": source_id, "Contact": get("Contact"),
                "Reason": "already imported, re-run is a no-op",
            })
            continue

        if not domain:
            held.append({
                "Source ID": source_id, "Contact": get("Contact"),
                "Reason": "no usable domain",
            })
            continue

        sheet_domain = website.lower().replace("https://", "").replace("www.", "")
        if domain != sheet_domain:
            notes.append(f"domain fixed ({sheet_domain} -> {domain})")

        if band and band != get("Employees"):
            notes.append(f"band fixed ({get('Employees')} -> {band})")

        # Company identity is the domain, not the name.
        if domain in companies:
            action = "attach to existing account"
            notes.insert(0, f"same company as {companies[domain]['first_contact']}, no 2nd deal")
        else:
            companies[domain] = {
                "Domain": domain, "Company name": account, "Employee range": band,
                "Segment": get("Segment"), "Source ID": source_id,
                "Deal name": f"{account} — New business",
                "first_contact": get("Contact"),
            }

        # Person identity is email. No email, no safe key.
        if not email:
            held.append({
                "Source ID": source_id, "Contact": get("Contact"),
                "Reason": "no email, and email is Attio's key for people",
            })
            continue

        people.append({
            "Email": email, "First name": first, "Last name": last,
            "Job title": get("Job title"), "LinkedIn": linkedin,
            "Company domain": domain, "Source ID": source_id,
            "Lead source": get("Lead source"), "Note": get("Research notes"),
            "_action": action, "_notes": notes, "_contact": get("Contact"),
        })

    return people, companies, held


def sheet_verdict(row):
    """What the current working sheet says: CHECK only if email is blank."""
    return "CHECK" if not (row.get("Work email") or "").strip() else "READY"


def report(rows, people, companies, held):
    by_source = {p["Source ID"]: p for p in people}
    held_by_source = {h["Source ID"]: h for h in held}

    print(f"\n  {len(rows)} rows in\n")
    print(f"  {'':2} {'CONTACT':<14} {'SHEET':<7} {'PIPELINE':<9} WHY")
    print("  " + "-" * 88)

    for i, row in enumerate(rows, 1):
        sid = (row.get("Source ID") or "").strip()
        contact = (row.get("Contact") or "").strip()
        sheet = sheet_verdict(row)

        if sid in held_by_source:
            verdict, why = "HOLD", held_by_source[sid]["Reason"]
        else:
            p = by_source.get(sid, {})
            verdict = "attach" if p.get("_action", "").startswith("attach") else "create"
            why = "; ".join(p.get("_notes", [])) or "clean"

        flag = " !" if (sheet == "READY" and verdict != "create") or why != "clean" else "  "
        print(f"  {flag} {contact:<14} {sheet:<7} {verdict:<9} {why[:58]}")

    print()
    print(f"  companies : {len(companies)}   (one per domain)")
    print(f"  deals     : {len(companies)}   (one per company, not per person)")
    print(f"  people    : {len(people)}")
    print(f"  held      : {len(held)}\n")


def write_csv(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path", nargs="?",
                    default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "notion-qualified-accounts-w34.csv"),
                    help="Notion CSV export. Defaults to the sample in this repo.")
    ap.add_argument("--out", default="out")
    args = ap.parse_args()

    rows = load(args.csv_path)
    people, companies, held = plan(rows)
    report(rows, people, companies, held)

    os.makedirs(args.out, exist_ok=True)
    write_csv(f"{args.out}/attio-companies.csv", list(companies.values()),
              ["Domain", "Company name", "Employee range", "Segment", "Source ID"])
    write_csv(f"{args.out}/attio-people.csv", people,
              ["Email", "First name", "Last name", "Job title", "LinkedIn",
               "Company domain", "Lead source", "Source ID", "Note"])
    write_csv(f"{args.out}/attio-deals.csv",
              [{"Deal name": c["Deal name"], "Company domain": c["Domain"]}
               for c in companies.values()],
              ["Deal name", "Company domain"])
    write_csv(f"{args.out}/review.csv", held, ["Source ID", "Contact", "Reason"])
    print("\n  Dry run. Nothing was sent to Attio.\n")


if __name__ == "__main__":
    main()
