import requests
from bs4 import BeautifulSoup
import json
import os

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
        if len(cells) < 3:
            continue
            
        # Extract wrestlers and result
        east_cell = cells[0]
        west_cell = cells[2]
        
        # Get wrestler names and IDs
        east_wrestler = extract_wrestler_info(east_cell)
        west_wrestler = extract_wrestler_info(west_cell)
        
        # Determine winner and kimarite
        kimarite = cells[1].text.strip()
        winner = None
        
        # Check for background color to determine winner
        east_style = east_cell.get('style', '')
        west_style = west_cell.get('style', '')
        
        if 'background-color' in east_style and 'background-color' not in west_style:
            winner = 'east'
        elif 'background-color' in west_style and 'background-color' not in east_style:
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
    basho = os.environ.get('BANZUKE')
    day = os.environ.get('DAY')
    output_file = 'matches.json'
    
    # Convert day to integer if provided
    if day:
        try:
            day = int(day)
        except ValueError:
            day = None
            print("Warning: DAY environment variable is not a valid integer")
    
    try:
        bouts = scrape_sumo_bouts(basho, day)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(bouts, f, indent=2, ensure_ascii=False)
        
        print(f"Successfully saved {len(bouts)} bouts to {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        # Exit with error code to fail the workflow
        exit(1)

if __name__ == "__main__":
    main()
