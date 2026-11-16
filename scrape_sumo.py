import requests
import json
import os
from datetime import datetime
import zoneinfo  # Python 3.9+
import calendar

_nskid_cache = {}


def get_current_basho_and_day():
    """Return the current basho (banzuke) and day based on Japan's date."""
    jst = zoneinfo.ZoneInfo("Asia/Tokyo")
    now = datetime.now(jst).date()

    tourney_months = [1, 3, 5, 7, 9, 11]

    year = now.year
    basho_start = None
    basho_month = None

    for m in reversed(tourney_months):
        start_date = second_sunday(year, m)
        if now >= start_date:
            basho_start = start_date
            basho_month = m
            break

    if basho_start is None:
        year -= 1
        basho_month = 11
        basho_start = second_sunday(year, basho_month)

    day = (now - basho_start).days + 1
    if day < 1 or day > 15:
        day = None

    banzuke = f"{year}{basho_month:02d}"
    return banzuke, day


def second_sunday(year, month):
    """Return the date of the second Sunday of a given month/year."""
    c = calendar.Calendar(firstweekday=calendar.SUNDAY)
    sundays = [day for day in c.itermonthdates(year, month)
               if day.weekday() == 6 and day.month == month]
    return sundays[1]


def get_nskid_for_wrestler(wrestler_id):
    """Fetch nskId for a wrestler from the rikishi API (with caching)."""
    if not wrestler_id:
        return None
    if wrestler_id in _nskid_cache:
        return _nskid_cache[wrestler_id]

    try:
        url = f"https://www.sumo-api.com/api/rikishi/{wrestler_id}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        nsk_id = data.get("nskId")
        _nskid_cache[wrestler_id] = nsk_id
        return nsk_id
    except Exception as e:
        print(f"Warning: Could not fetch nskId for wrestler {wrestler_id}: {e}")
        return None


def get_head_to_head(east_id, west_id):
    """Fetch historic head-to-head record between two wrestlers."""
    if not east_id or not west_id:
        return None

    try:
        url = f"https://www.sumo-api.com/api/rikishi/{east_id}/matches/{west_id}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        east_wins = data.get("rikishiWins")
        west_wins = data.get("opponentWins")

        # Fallback: count directly from matches list if summary fields are absent
        if east_wins is None or west_wins is None:
            matches = data.get("matches") or []
            east_wins = sum(1 for m in matches if m.get("winnerId") == east_id)
            west_wins = sum(1 for m in matches if m.get("winnerId") == west_id)

        return {
            "eastWins": east_wins,
            "westWins": west_wins,
        }
    except Exception as e:
        print(f"Warning: Could not fetch head-to-head for {east_id} vs {west_id}: {e}")
        return None


def scrape_sumo_bouts(basho=None, day=None):
    """Fetch sumo bouts from the sumo-api.com API."""
    if not basho or not day:
        raise ValueError("basho and day parameters are required")

    base_url = f"https://www.sumo-api.com/api/basho/{basho}/torikumi/Makuuchi/{day}"

    response = requests.get(base_url, timeout=15)
    response.raise_for_status()

    data = response.json()

    if not isinstance(data, dict):
        raise ValueError(f"Unexpected API response format: expected dict, got {type(data)}")

    bouts_data = data.get("torikumi", [])
    if not isinstance(bouts_data, list):
        raise ValueError(f"Expected 'torikumi' to be a list, got {type(bouts_data)}")

    bouts = []
    for bout in bouts_data:
        east_id = bout.get("eastId")
        west_id = bout.get("westId")
        winner_id = bout.get("winnerId")

        bouts.append({
            "east": {
                "name": bout.get("eastShikona", ""),
                "id": get_nskid_for_wrestler(east_id)
            },
            "west": {
                "name": bout.get("westShikona", ""),
                "id": get_nskid_for_wrestler(west_id)
            },
            "kimarite": bout.get("kimarite", None) or None,
            "winner": get_nskid_for_wrestler(winner_id) if winner_id else None,
            "history": get_head_to_head(east_id, west_id)
        })

    return bouts


def check_missing_images(bouts, images_dir="images"):
    """Check which rikishi in today's bouts are missing photos in images/."""
    missing = {}
    for bout in bouts:
        for side in ("east", "west"):
            wrestler = bout.get(side, {})
            nsk_id = wrestler.get("id")
            name = wrestler.get("name", "Unknown")
            if not nsk_id:
                continue
            img_path = os.path.join(images_dir, f"{nsk_id}.jpg")
            if not os.path.exists(img_path):
                missing[nsk_id] = name

    if missing:
        print(f"\nMissing {len(missing)} rikishi image(s) in '{images_dir}/':")
        for nsk_id, name in missing.items():
            print(f"  - {name} (ID: {nsk_id}) -> https://sumo.or.jp/EnSumoDataRikishi/profile/{nsk_id}/")
    else:
        print(f"\nAll rikishi images for today's bouts are present in '{images_dir}/'.")


def main():
    basho = os.environ.get('BANZUKE')
    day = os.environ.get('DAY')
    if not basho or not day:
        basho, day = get_current_basho_and_day()
        print("incomplete basho data, using automatic")

    print(f"Using banzuke {basho}, day {day}")
    if day:
        try:
            day = int(day)
        except ValueError:
            day = None
            print("Warning: DAY environment variable is not a valid integer")

    try:
        bouts = scrape_sumo_bouts(basho, day)
        output_file = 'matches.json'

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(bouts, f, indent=2, ensure_ascii=False)

        print(f"Successfully saved {len(bouts)} bouts to {output_file}")
        check_missing_images(bouts)

    except Exception as e:
        print(f"Error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
