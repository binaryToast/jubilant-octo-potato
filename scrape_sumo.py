import requests
from bs4 import BeautifulSoup
from datetime import date, timedelta, datetime
import json

BASHO_MONTHS = [1, 3, 5, 7, 9, 11]
TOURNAMENT_DAYS = 15

def second_sunday(year, month):
    first = date(year, month, 1)
    # weekday(): Monday=0 ... Sunday=6
    days_until_sunday = (6 - first.weekday()) % 7
    first_sunday = first + timedelta(days=days_until_sunday)
    second_sun = first_sunday + timedelta(days=7)
    return second_sun

def get_current_banzuke_day(today=None):
    if today is None:
        today = date.today()
    year = today.year
    # find most recent banzuke month <= current month
    months = [m for m in BASHO_MONTHS if m <= today.month]
    if months:
        b_month = max(months)
        b_year = year
    else:
        b_month = 11
        b_year = year - 1

    banzuke = f"{b_year}{b_month:02d}"
    start_day = second_sunday(b_year, b_month)
    day = (today - start_day).days + 1
    day = max(1, min(day, TOURNAMENT_DAYS))
    return banzuke, day

def fetch_makuuchi_matches(banzuke, day):
    url = f"https://sumodb.sumogames.de/Results.aspx?b={banzuke}&d={day}"
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')

    # Makuuchi section usually has h2 with "Makuuchi"
    matches = []
    section = soup.find('h2', string='Makuuchi')
    if not section:
        print("Could not find Makuuchi section")
        return matches

    # The Makuuchi table is the next sibling after the h2
    table = section.find_next('table')
    if not table:
        print("Could not find Makuuchi table")
        return matches

    rows = table.find_all('tr')
    bout_num = 1
    for row in rows:
        cells = row.find_all('td')
        if len(cells) < 4:
            continue
        east = cells[0].get_text(strip=True)
        west = cells[1].get_text(strip=True)
        result_cell = cells[3].get_text(strip=True)
        winner = None
        if result_cell:
            # If result is something like "W", assume East won; "L" = West won
            # Or detect "○" vs "●" if symbols used
            if "○" in result_cell or "W" in result_cell:
                winner = east
            elif "●" in result_cell or "L" in result_cell:
                winner = west
        matches.append({
            "bout": bout_num,
            "east": east,
            "west": west,
            "winner": winner,
        })
        bout_num += 1
    return matches

def main():
    banzuke, day = get_current_banzuke_day()
    matches = fetch_makuuchi_matches(banzuke, day)
    output = {
        "banzuke": banzuke,
        "day": day,
        "fetched_at_utc": datetime.utcnow().isoformat() + "Z",
        "matches": matches
    }
    with open("matches.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(matches)} Makuuchi bouts to matches.json")

if __name__ == "__main__":
    main()
