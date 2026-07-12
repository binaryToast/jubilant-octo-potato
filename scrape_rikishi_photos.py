#!/usr/bin/env python3
"""
Script to scrape rikishi (sumo wrestler) photos from the official sumo website.
Extracts wrestler IDs from matches.json and downloads their photos.
"""

import json
import os
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin
from typing import Set

# Constants
MATCHES_FILE = "matches.json"
IMAGES_DIR = "images"
BASE_URL = "https://www.sumo.or.jp/EnSumoDataRikishi/profile"

def create_images_directory():
    """Create the images directory if it doesn't exist."""
    Path(IMAGES_DIR).mkdir(exist_ok=True)
    print(f"Ensured {IMAGES_DIR} directory exists")

def extract_wrestler_ids() -> Set[int]:
    """Extract unique wrestler IDs from matches.json."""
    with open(MATCHES_FILE, 'r') as f:
        matches = json.load(f)
    
    ids = set()
    for match in matches:
        if 'east' in match and 'id' in match['east']:
            ids.add(match['east']['id'])
        if 'west' in match and 'id' in match['west']:
            ids.add(match['west']['id'])
    
    print(f"Found {len(ids)} unique wrestler IDs")
    return ids

def scrape_photo_url(wrestler_id: int) -> str:
    """
    Scrape the rikishi photo URL from the sumo.or.jp website.
    
    Args:
        wrestler_id: The wrestler's ID number
        
    Returns:
        The photo URL if found, None otherwise
    """
    url = f"{BASE_URL}/{wrestler_id}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for the photo image element
        # The photo is typically in an img tag with class 'rikishi_photo' or similar
        photo_img = soup.find('img', class_='rikishi_photo')
        
        if not photo_img:
            # Try alternative selectors
            photo_img = soup.find('img', class_=lambda x: x and 'photo' in x.lower())
        
        if photo_img and photo_img.get('src'):
            photo_url = photo_img['src']
            # Handle relative URLs
            if photo_url.startswith('/'):
                photo_url = urljoin("https://www.sumo.or.jp", photo_url)
            elif not photo_url.startswith('http'):
                photo_url = urljoin(url, photo_url)
            return photo_url
        
        print(f"Warning: No photo found for wrestler ID {wrestler_id}")
        return None
        
    except requests.RequestException as e:
        print(f"Error fetching profile for wrestler ID {wrestler_id}: {e}")
        return None

def download_photo(wrestler_id: int, photo_url: str) -> bool:
    """
    Download a photo and save it with the wrestler ID as filename.
    
    Args:
        wrestler_id: The wrestler's ID number
        photo_url: The URL of the photo to download
        
    Returns:
        True if successful, False otherwise
    """
    try:
        response = requests.get(photo_url, timeout=10)
        response.raise_for_status()
        
        # Save the image
        filename = os.path.join(IMAGES_DIR, f"{wrestler_id}.jpg")
        with open(filename, 'wb') as f:
            f.write(response.content)
        
        print(f"Downloaded photo for wrestler ID {wrestler_id}")
        return True
        
    except requests.RequestException as e:
        print(f"Error downloading photo for wrestler ID {wrestler_id}: {e}")
        return False

def main():
    """Main execution function."""
    print("Starting rikishi photo scraper...")
    
    # Create images directory
    create_images_directory()
    
    # Extract wrestler IDs from matches.json
    wrestler_ids = extract_wrestler_ids()
    
    # Scrape and download photos for each wrestler
    successful = 0
    failed = 0
    
    for wrestler_id in sorted(wrestler_ids):
        photo_url = scrape_photo_url(wrestler_id)
        if photo_url:
            if download_photo(wrestler_id, photo_url):
                successful += 1
            else:
                failed += 1
        else:
            failed += 1
    
    print(f"\nScraping complete!")
    print(f"Successfully downloaded: {successful}")
    print(f"Failed: {failed}")

if __name__ == "__main__":
    main()
