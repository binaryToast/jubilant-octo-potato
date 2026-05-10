import requests
import json
import os
from datetime import datetime, timedelta
import zoneinfo  # Python 3.9+
import calendar

def get_current_basho_and_day():
    """Return the current basho (banzuke) and day based on Japan's date."""
    # 1. Current time in Japan
    jst = zoneinfo.ZoneInfo("Asia/Tokyo")
    now = datetime.now(jst).date()

    # 2. Tournament months (odd months starting Jan)
    tourney_months = [1, 3, 5, 7, 9, 11]

    # 3. Find the most recent tournament start
    year = now.year
    basho_start = None
    basho_month = None

    for m in reversed(tourney_months):
        start_date = second_sunday(year, m)
        if now >= start_date:
            basho_start = start_date
            basho_month = m
            break
    # If we're before January basho this year, roll back to previous November
    if basho_start is None:
        year -= 1
        basho_month = 11
        basho_start = second_sunday(year, basho_month)

    # 4. Compute day of tournament (1–15)
    day = (now - basho_start).days + 1
    if day < 1 or day > 15:
        day = None  # Outside active days

    # 5. Make a banzuke code (e.g., 202509 for Sep 2025 basho)
    banzuke = f"{year}{basho_month:02d}"

    return banzuke, day

def second_sunday(year, month):
    """Return the date of the second Sunday of a given month/year."""
    c = calendar.Calendar(firstweekday=calendar.SUNDAY)
    sundays = [day for day in c.itermonthdates(year, month)
               if day.weekday() == 6 and day.month == month]
    return sundays[1]

def get_nskid_for_wrestler(wrestler_id):
    """Fetch nskId for a wrestler from the rikishi API."""
    try:
        url = f"https://www.sumo-api.com/api/rikishi/{wrestler_id}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get("nskId")
    except Exception as e:
        print(f"Warning: Could not fetch nskId for wrestler {wrestler_id}: {e}")
        return None

def scrape_sumo_bouts(basho=None, day=None):
    """Fetch sumo bouts from the sumo-api.com API."""
    if not basho or not day:
        raise ValueError("basho and day parameters are required")
    
    base_url = f"https://www.sumo-api.com/api/basho/{basho}/torikumi/Makuuchi/{day}"
    
    response = requests.get(base_url)
    response.raise_for_status()
    
    data = response.json()
    
    # The API returns a dict with torikumi containing the list of bouts
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
            "winner": get_nskid_for_wrestler(winner_id) if winner_id else None
        })
    
    return bouts

def main():
    # Get parameters from environment variables (for GitHub Actions)
    # auto_banzuke, auto_day = get_current_basho_and_day()
    basho = os.environ.get('BANZUKE')
    day = os.environ.get('DAY')
    if not basho or not day:
        basho, day = get_current_basho_and_day()
        print(f"incomplete basho data, using automatic")
        
    print(f"Using banzuke {basho}, day {day}")
    # Convert day to integer if provided
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
        
    except Exception as e:
        print(f"Error: {e}")
        # Exit with error code to fail the workflow
        exit(1)

if __name__ == "__main__":
    main()
