thonimport time
import json
import requests
from extractors.linkedin_parser import parse_linkedin_search_page
from outputs.exporters import export_to_json
from config.settings import get_config

def run_scraper():
    config = get_config()
    session_cookies = config['linkedin_session_cookies']
    search_url = config['linkedin_search_url']
    max_profiles = config['max_profiles']
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    profiles = []
    current_page = 1
    while len(profiles) < max_profiles:
        response = requests.get(search_url, headers=headers, cookies=session_cookies)
        if response.status_code == 200:
            new_profiles = parse_linkedin_search_page(response.text)
            profiles.extend(new_profiles)
            if len(profiles) >= max_profiles:
                break
            current_page += 1
            time.sleep(2)  # Random delay for human-like behavior
        else:
            print(f"Error fetching page {current_page}, status code: {response.status_code}")
            break

    export_to_json(profiles, 'output.json')

if __name__ == "__main__":
    run_scraper()