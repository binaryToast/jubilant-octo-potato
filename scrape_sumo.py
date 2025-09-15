#!/usr/bin/env python3
"""
scrape_sumo.py

Scrapes Makuuchi matches from SumoDB Results_text.aspx for a given banzuke/day.

Usage:
  - Local test with explicit banzuke/day:
      python scrape_sumo.py --banzuke 202509 --day 2

  - Or set environment variables (used by the workflow):
      BANZUKE=202509 DAY=2 python scrape_sumo.py

If neither provided, the script:
  - chooses the most recent banzuke month (Jan,Mar,May,Jul,Sep,Nov)
  - finds the SECOND SUNDAY of that month (day 1)
  - computes day = (today - second_sunday) + 1
  - caps day between 1 and 15
"""
from datetime import date, datetime, timedelta
import argparse
import os
import requests
from bs4 import BeautifulSoup
import json
import re
import sys

BASHO_MONTHS = [1, 3, 5, 7, 9, 11]
TOURNAMENT_DAYS = 15

def second_sunday_of(year, month):
    first = date(year, month, 1)
    # weekday(): Monday=0 ... Sunday=6
    days_until_sunday = (6 - first.weekday()) % 7
    first_sunday = first + timedelta(days=days_until_sunday)
    second_sunday = first_sunday + timedelta(days=7)
    return second_sunday

def choose_banzuke_and_day(today):
    # find latest banzuke month <= today.month; otherwise go to previous year's Nov
    year = today.year
    possible = [m for m in BASHO_MONTHS if m <= today.month]
    if possible:
        b_month = max(possible)
        b_year = year
    else:
        b_month = 11
        b_year = year - 1

    second_sun = second_sunday_of(b_year, b_month)
    day = (today - second_sun).days + 1
    if day < 1:
        # If today before second Sunday, default to day 1 (useful for tests/upcoming basho)
        day = 1
    if day > TOURNAMENT_DAYS:
        day = TOURNAMENT_DAYS
    banzuke = f"{b_year}{b_month:02d}"
    return banzuke, day

def parse_matches_from_text(text):
    """
    Extract lines between 'Makuuchi' and 'Juryo'. Return list of dicts:
    { day, bout, east, west, winner, raw }
    The parser tries to split columns by two-or-more spaces (common in text export).
    If parsing fails for a line, we include the raw line so frontend can still show it.
    """
    lines = [l.rstrip() for l in text.splitlines() if l.strip()]
    matches = []
    capture = False
    bout_num = 1
    for line in lines:
        if line.startswith("Makuuchi"):
            capture = True
            continue
        if not capture:
            continue
        if line.startswith("Juryo"):
            break

        raw = line
        east = None
        west = None
        winner = None

        # look for asterisk marking winner
        if "*" in line:
            # determine which side contains the star
            # remove star for name extraction
            clean_line = line.replace("*", "")
            # but keep a marker for later
            star_side = 'both' if line.count("*") > 1 else None
        else:
            clean_line = line
            star_side = None

        # split by two or more spaces (text export columns)
        cols = re.split(r'\s{2,}', clean_line.strip())
        try:
            if len(cols) >= 2:
                left = cols[0].strip()
                right = cols[1].strip()
                # remove leading bout/rank numbers from left (e.g. "1 Hoshoryu")
                left = re.sub(r'^\d+\s*', '', left)
                # remove trailing records like "10-5" from names if present
                left = re.sub(r'\s+\d+-\d+.*$', '', left).strip()
                right = re.sub(r'\s+\d+-\d+.*$', '', right).strip()
                # If right contains parentheses or extra notes, strip them
                right = re.sub(r'\s*\(.*$', '', right).strip()

                east = left if left else None
                west = right if right else None

                # find winner if we detected the asterisk in original
                if "*" in line:
                    # if the asterisk was in the left part of the original line, mark east
                    # crude check: see which column contains '*' in original line
                    orig_cols = re.split(r'\s{2,}', line.strip())
                    if len(orig_cols) >= 2:
                        if "*" in orig_cols[0]:
                            winner = east
                        elif "*" in orig_cols[1]:
                            winner = west
            else:
                # fallback: try to split by " - " or " vs "
                m = re.split(r'\s+-\s+|\s+vs\.?\s+|\s+v\s+', clean_line)
                if len(m) >= 2:
                    east = re.sub(r'^\d+\s*', '', m[0]).strip()
                    west = re.sub(r'\s+\d+-\d+.*$', '', m[1]).strip()
        except Exception:
            east = None
            west = None

        matches.append({
            "bout": bout_num,
            "east": east,
            "west": west,
            "winner": winner,
            "raw": raw
        })
        bout_num += 1

    return matches

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--banzuke", help="YYYYMM banzuke code (override)", type=str)
    parser.add_argument("--day", help="day number (override)", type=int)
    args = parser.parse_args()

    # priority: CLI args -> env vars -> computed
    banzuke = args.banzuke or os.getenv("BANZUKE")
    day = args.day or (int(os.getenv("DAY")) if os.getenv("DAY") else None)

    today_utc = datetime.utcnow().date()

    if not banzuke or not day:
        computed_banzuke, computed_day = choose_banzuke_and_day(today_utc)
        if not banzuke:
            banzuke = computed_banzuke
        if not day:
            day = computed_day

    # Safety caps
    try:
        day = int(day)
    except Exception:
        print("Invalid day value:", day, file=sys.stderr)
        sys.exit(2)

    if day < 1:
        day = 1
    if day > TOURNAMENT_DAYS:
        day = TOURNAMENT_DAYS

    print(f"Fetching banzuke={banzuke} day={day}")

    url = f"https://sumodb.sumogames.de/Results_text.aspx?b={banzuke}&d={day}"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    page_text = soup.get_text()
    matches = parse_matches_from_text(page_text)

    # Add top-level metadata
    output = {
        "banzuke": banzuke,
        "day": day,
        "fetched_at_utc": datetime.utcnow().isoformat() + "Z",
        "matches": matches
    }

    with open("matches.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(matches)} bouts to matches.json")

if __name__ == "__main__":
    main()
