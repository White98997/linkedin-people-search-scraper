thonfrom bs4 import BeautifulSoup

def parse_linkedin_search_page(page_html):
    soup = BeautifulSoup(page_html, 'html.parser')
    profiles = []

    results = soup.find_all('div', class_='search-result')
    for result in results:
        profile = {
            "fullName": result.find('span', class_='actor-name').text.strip(),
            "headline": result.find('p', class_='subline-level-1').text.strip(),
            "location": result.find('p', class_='subline-level-2').text.strip(),
            "profileUrl": result.find('a')['href']
        }
        profiles.append(profile)

    return profiles