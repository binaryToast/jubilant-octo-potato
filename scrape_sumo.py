import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import os

# --- CONFIG ---
# determine today's banzuke code and day automatically
# Sumo basho months: Jan, Mar, May, Jul, Sep, Nov
# banzuke code is YYYYMM where MM is the basho month
today = datetime.utcnow().date()  # or use JST if you prefer
year = today.year

# find the last basho month <= current month
bashos = [1,3,5,7,9,11]
month = max(m for m in bashos if m <= today.month)
banzuke = f"{year}{month:02d}"

# day of basho = difference from start date; adjust if needed
# We'll just guess day by counting days since Sunday start:
# (official tournaments start Sunday)
start_guess = datetime(year, month, 1)
while start_guess.weekday() != 6:  # find first Sunday
    start_guess = start_guess.replace(day=start_guess.day+1)
day = (today - start_guess.date()).days + 1
if day < 1: 
    day = 1

print(f"Fetching banzuke={banzuke} day={day}")

url = f"https://sumodb.sumogames.de/Results_text.aspx?b={banzuke}&d={day}"
resp = requests.get(url)
resp.raise_for_status()

soup = BeautifulSoup(resp.text, "html.parser")
lines = [l.strip() for l in soup.get_text().splitlines() if l.strip()]

matches = []
capture = False
bout_num = 1
for line in lines:
    if line.startswith("Makuuchi"):
        capture = True
        continue
    if capture:
        if line.startswith("Juryo"):
            break
        # SumoDB line format: "East Rikishi x-y West Rikishi" plus result info
        # We’ll split by double space to isolate East and West
        parts = line.split()
        # a simple parse: East name first, West name last
        # (this is crude but works for placeholder)
        east = parts[0]
        west = parts[-1]
        winner = None
        if "*" in line:  # SumoDB marks winner with *
            # The winner’s name will have an asterisk appended
            if "*" in east:
                east = east.replace("*","")
                winner = east
            if "*" in west:
                west = west.replace("*","")
                winner = west
        matches.append({
            "day": day,
            "bout": bout_num,
            "east": east,
            "west": west,
            "winner": winner
        })
        bout_num += 1

# Write matches.json
with open("matches.json","w",encoding="utf-8") as f:
    json.dump(matches,f,ensure_ascii=False,indent=2)

print(f"Wrote {len(matches)} bouts to matches.json")
