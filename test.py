import requests
from bs4 import BeautifulSoup
import trafilatura
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

def extract_static(url, min_length=1000):
    """Fast static extraction using trafilatura."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        html = resp.text
        metadata = trafilatura.extract_metadata(html)
        title = metadata.as_dict().get('title', 'No title') if metadata else 'No title'
        text = trafilatura.extract(html, include_formatting=False) or ''
        text = ' '.join(text.split())
        if len(text) >= min_length:
            return title, text
        return None, None
    except Exception as e:
        print(f"Static error: {e}")
        return None, None

def extract_dynamic(url):
    """Dynamic extraction using Selenium."""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    try:
        driver.get(url)
        time.sleep(10)  # Wait for JS load
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        print ("soup: ", soup )
        print (soup.find('h1', class_='headline').string.strip())
        title = soup.find('h1', class_='headline').string.strip() if soup.find('h1', class_='headline') else soup.title.string.strip() if soup.title else "No title found"
        #title = soup.title.string.strip() if soup.title else "No title found"
        
        article_elem = (
            soup.find('article') or 
            soup.find('div', class_='c-post-content') or  # Global News specific
            soup.find('div', class_='news-release-content') or 
            soup.find('div', class_='content') or 
            soup.find('div', id='content') or 
            soup.body
        )
        text = ' '.join(article_elem.get_text().split()) if article_elem else "No article text found"
        return title, text
    finally:
        driver.quit()

def extract_content(url, min_length=1000):
    """Generic extractor: static first, dynamic fallback."""
    title, text = extract_static(url, min_length)
    if title and text:
        print(f"Used static extraction: {len(text)} chars")
        return title, text
    
    print("Falling back to dynamic extraction...")
    title, text = extract_dynamic(url)
    print(f"Used dynamic extraction: {len(text)} chars")
    return title, text

# Usage: Works for any URL
if __name__ == "__main__":
    # Test with Global News (static)
    url1 = 'https://globalnews.ca/news/11454042/mark-carney-canada-post-strike-cupw/'
    title1, text1 = extract_content(url1)
    print(f"\nURL1 Title: {title1}")
    print(f"URL1 Text (first 200 chars): {text1[:200] if text1 else ''}")

    # Test with Issuer Direct (dynamic)
    url2 = 'https://feeds.issuerdirect.com/news-release.html?newsid=7873893141691513&symbol=BB,BB:CA'
    title2, text2 = extract_content(url2)
    print(f"\nURL2 Title: {title2}")
    print(f"URL2 Text (first 200 chars): {text2[:200] if text2 else ''}")