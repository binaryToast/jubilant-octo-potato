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
    
    # Find Makuuchi table by caption
    makuuchi_table = None
    for table in soup.find_all('table', class_='tk_table'):
        caption = table.find('caption')
        if caption and 'Makuuchi' in caption.text:
            makuuchi_table = table
            break
    
    if not makuuchi_table:
        raise ValueError("Makuuchi table not found")
    
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
        if 'background-color' in east_cell.get('style', ''):
            winner = 'east'
        elif 'background-color' in west_cell.get('style', ''):
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
        return {
            "name": link.text.strip(),
            "id": link['href'].split('=')[-1]
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
