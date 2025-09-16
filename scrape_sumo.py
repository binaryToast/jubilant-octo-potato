import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime, timedelta
import zoneinfo  # Python 3.9+
import calendar

def get_yusho_arasoi_data():
    """
    Scrapes the Makuuchi Yusho Arasoi table from https://sumodb.sumogames.de/Banzuke.aspx
    and returns a dict grouping rikishi by current win count.
    Output format:
    {
        "10": ["Hoshoryu 10-2", "Takakeisho 10-2"],
        "9": ["Wakamotoharu 9-3", ...],
        ...
    }
    """
    url = "https://sumodb.sumogames.de/Banzuke.aspx"
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    # Find the left column (should have Yusho arasoi)
    header = soup.find("h3", string=lambda s: s and "Yusho arasoi" in s)
    if not header:
        raise RuntimeError("Could not find Yusho arasoi header")
    table = header.find_next("table")
    if not table:
        raise RuntimeError("Could not find Yusho arasoi table")

    records = {}
    for row in table.find_all("tr")[1:]:  # skip table header
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        name = cells[1].get_text(strip=True)
        record = cells[2].get_text(strip=True)
        wins = record.split('-')[0]
        try:
            wins_int = int(wins)
        except ValueError:
            continue
        entry = f"{name} {record}"
        records.setdefault(wins, []).append(entry)

    # Sort by descending win count, and names alphabetically within each group
    sorted_records = {
        str(w): sorted(records[str(w)]) for w in sorted(records.keys(), key=int, reverse=True)
    }
    return sorted_records

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

def scrape_sumo_bouts(basho=None, day=None):
    base_url = "https://sumodb.sumogames.de/Results.aspx"
    params = {}
    if basho and day:
        params = {"b": basho, "d": day}
    
    response = requests.get(base_url, params=params)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Get the first table with class 'tk_table' (Makuuchi is the top division)
    makuuchi_table = soup.find('table', class_='tk_table')
    
    if not makuuchi_table:
        raise ValueError("No sumo bout table found on the page")
    
    bouts = []
    for row in makuuchi_table.find_all('tr')[1:]:  # Skip header row
        cells = row.find_all('td')
        
        # Skip rows that don't have enough cells for a bout
        if len(cells) < 5:
            continue
            
        # Extract information from the correct columns
        # Column 1: East result (hoshi_shiro.gif for win, hoshi_kuro.gif for loss)
        # Column 2: East rikishi
        # Column 3: Kimarite
        # Column 4: West rikishi
        # Column 5: West result
        
        east_result_cell = cells[0]
        east_rikishi_cell = cells[1]
        kimarite_cell = cells[2]
        west_rikishi_cell = cells[3]
        west_result_cell = cells[4]
        
        # Get wrestler names and IDs
        east_wrestler = extract_wrestler_info(east_rikishi_cell)
        west_wrestler = extract_wrestler_info(west_rikishi_cell)
        
        # Determine winner based on result images
        winner = None
        kimarite = kimarite_cell.text.strip()
        
        # Check for win/loss images
        east_win = east_result_cell.find('img', src=lambda x: x and 'hoshi_shiro.gif' in x)
        east_loss = east_result_cell.find('img', src=lambda x: x and 'hoshi_kuro.gif' in x)
        west_win = west_result_cell.find('img', src=lambda x: x and 'hoshi_shiro.gif' in x)
        west_loss = west_result_cell.find('img', src=lambda x: x and 'hoshi_kuro.gif' in x)
        
        if east_win and west_loss:
            winner = 'east'
        elif west_win and east_loss:
            winner = 'west'
        
        # For future bouts, kimarite might be empty
        if kimarite == '-' or not kimarite:
            kimarite = None
            winner = None
        
        bouts.append({
            "east": east_wrestler,
            "west": west_wrestler,
            "kimarite": kimarite,
            "winner": winner
        })
    
    return bouts

def extract_wrestler_info(cell):
    link = cell.find('a')
    if link:
        href = link.get('href', '')
        wrestler_id = href.split('=')[-1] if '=' in href else None
        return {
            "name": link.text.strip(),
            "id": wrestler_id
        }
    return {"name": cell.text.strip(), "id": None}

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
        leaders = get_yusho_arasoi_data()
        output_file = 'matches.json'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(bouts, f, indent=2, ensure_ascii=False)
        
        output_file = 'leaders.json'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(leaders, f, indent=2, ensure_ascii=False)
        
        print(f"Successfully saved {len(bouts)} bouts to {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        # Exit with error code to fail the workflow
        exit(1)

if __name__ == "__main__":
    main()
