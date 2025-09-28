from flask_cors import CORS
from flask import Flask, request, jsonify, Response
import requests
from bs4 import BeautifulSoup
import json
import os
import re
import config
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

LLM_API_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
LLM_API_MODEL = "x-ai/grok-4-fast:free"

def parse_llm_response(json_response):
    try:
        # Parse the JSON string into a Python dictionary
        response_dict = json.loads(json_response)
        
        # Extract the content from the first choice's message
        content = response_dict['choices'][0]['message']['content']
        # Split the content by newlines to isolate Summary and Sentiment
        lines = content.split('\n')
        
        summary = None
        sentiment = None
        
        for line in lines:
            if line.startswith('Summary:'):
                # Join all lines that belong to the summary until we hit an empty line or another section
                summary_parts = []
                i = lines.index(line) + 1
                while i < len(lines) and lines[i] and not lines[i].startswith(('Sentiment:', 'Summary:')):
                    summary_parts.append(lines[i].strip())
                    i += 1
                summary = '\n'.join(summary_parts)
            elif line.startswith('Sentiment:'):
                sentiment = line.split(':', 1)[1].strip()
        
        return summary, sentiment
    except (ValueError, KeyError, IndexError) as e:
        # Handle potential JSON parsing errors or missing keys
        print(f"Error parsing response: {e}")
        return None

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
        #print ("soup: ", soup )
        #print (soup.find('h1', class_='headline').string.strip())
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

@app.route('/analyze', methods=['POST'])
def analyze_urls():

    try:
        data = request.get_json()
        urls = data.get('urls')
        if not urls:
            return jsonify({'error': 'No URLs provided'}), 400

        results = []
        for url in urls:
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                }   

                response = requests.get(url, headers=headers)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                title = soup.title.string if soup.title else "No title found"
                article_text = ' '.join(soup.get_text().split())

                if len(article_text) < 50:
                    title, article_text = extract_dynamic(url)
                
                llmHeaders = {
                    "Authorization": f"Bearer {config.LLM_API_KEY}",
                    "Content-Type": "application/json"
                }  
                payload = {
                    "model": LLM_API_MODEL,
                    "messages": [
                        {"role": "user", "content": f"""
                            Article content:
                            {article_text} 

                            Please summarize this article in exactly 2-3 sentences using bullet points. Use ^ in front of each bullet points. Then, provide the sentiment of the summary with one of these words: positive, neutral, negative. Format your response like this:
                                Summary:
                                    ^ [Sentence 1]
                                    ^ [Sentence 2]
                                    ^ [Sentence 3] (optional)

                                Sentiment: [Positive, Neutral, or Negative]"""
                        }]
                }
                llm_response = requests.post(LLM_API_ENDPOINT, headers=llmHeaders, data=json.dumps(payload))
                llm_response.raise_for_status()
                summary, sentiment = parse_llm_response(llm_response.text)
                
                results.append({
                    'name': title,
                    'summary': summary,
                    'sentiment': sentiment,
                    'url': url,
                })

            except requests.exceptions.RequestException as e:
                results.append({
                    'name': "N/A",
                    'summary': None,
                    'sentiment': None,
                    'url': url,
                    'error': f'Error fetching URL: {e}'
                })
            except json.JSONDecodeError as e:
                results.append({
                    'name': "N/A",
                    'summary': None,
                    'sentiment': None,
                    'url': url,
                    'error': f'Error decoding Ollama response: {e}'
                })
            except Exception as e:
                results.append({
                    'name': "N/A",
                    'summary': None,
                    'sentiment': None,
                    'url': url,
                    'error': f'An unexpected error occurred: {e}'
                })

        return jsonify(results)

    except json.JSONDecodeError as e:
        return jsonify({'error': f'Invalid JSON input: {e}'}), 400
    except Exception as e:
        return jsonify({'error': f'An unexpected error occurred: {e}'}), 500

if __name__ == '__main__':
    app.run(debug=True)
