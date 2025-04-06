from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup as bs
import google.generativeai as genai
import logging
from typing import List, Dict
from functools import lru_cache
from markupsafe import Markup
import re
import os
from dotenv import load_dotenv

# Load the .env file
load_dotenv()


# ------------------ Configuration ------------------ #
logging.basicConfig(
    level=logging.INFO,
    filename='phone_recommender.log',
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Gemini API setup
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY not set.")
    raise ValueError("GEMINI_API_KEY is required")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

app = Flask(__name__)

# ------------------ Scraper ------------------ #
@lru_cache(maxsize=100)
def cached_fetch_phones(query: str) -> List[Dict]:
    return fetch_phones_from_flipkart(query)

def fetch_phones_from_flipkart(query: str, max_phones: int = 20) -> List[Dict]:
    url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}&sort=price_asc"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    try:
        logger.info(f"Fetching URL: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        soup = bs(response.content, 'html.parser')

        phone_data = []
        seen_titles = set()
        cards = soup.find_all('a', {'class': 'CGtC98'})

        for card in cards:
            title_tag = card.find('div', {'class': 'Otbq5D'})
            title = title_tag.img['alt'] if title_tag and title_tag.img else 'N/A'

            if title in seen_titles:
                continue
            seen_titles.add(title)

            href = card.get('href', '')
            full_link = f"https://www.flipkart.com{href}"

            price = 0
            price_tag = card.find('div', class_=['Nx9bqj', 'CxhGGd']) or card.find('div', class_='_30jeq3')

            if price_tag:
                try:
                    price = int(price_tag.text.replace('₹', '').replace(',', '').strip())
                except:
                    pass

           
            img_tag = card.find('img', {'class': 'DByuf4'})
            img_url = img_tag['src'] if img_tag else ''

            # ✅ Fetch full spec list (features)
            spec_tags = card.find_all('li')
            specs = [li.get_text(strip=True) for li in spec_tags if li.get_text(strip=True)]
            print(spec_tags)
            # Append everything
            phone_data.append({
                "title": title,
                "price": price,
                "specs": specs,
                "url": full_link,
                "image": img_url
            })

            if len(phone_data) >= max_phones:
                break
        return phone_data

    except Exception as e:
        logger.error(f"Scraping error: {e}")
        return []

# # ------------------ Scoring & Gemini ------------------ #
# def score_phone(phone: Dict, user_input: Dict) -> float:
#     score = 0
#     specs = " ".join(phone["specs"]).lower()

#     if phone["price"] > int(user_input["budget"]):
#         return 0

#     score += 20
#     if user_input["ram"].lower() in specs: score += 15
#     if user_input["rom"].lower() in specs: score += 15
#     if user_input["camera"].lower() in specs: score += 10
#     if user_input["processor"].lower() in specs: score += 10
#     if user_input["display"].lower() in specs: score += 5
#     if user_input["battery"].lower() in specs: score += 5
#     if user_input["ir"] == "yes" and "ir blaster" in specs: score += 5
#     if user_input["nfc"] == "yes" and "nfc" in specs: score += 5
#     if user_input["brands"].lower() in phone["title"].lower(): score += 10

#     return score


# def build_prompt(user_input: Dict, phones: List[Dict]) -> str:
#     phone_lines = []
#     for idx, phone in enumerate(phones[:3], 1):
#         phone_lines.append(f"{idx}. **{phone['title']}**\n"
#                            f"   - Price: ₹{phone['price']}\n"
#                            f"   - URL: {phone['url']}\n"
#                            f"   - Image: {phone['image']}\n")

#     phones_text = "\n".join(phone_lines)

#     return f"""
# You are a smartphone advisor AI. A user is looking for phones with these preferences:

# - Budget: ₹{user_input['budget']}
# - Usage: {user_input['usage']}
# - Brand Preference: {user_input['brands']}
# - RAM: {user_input['ram']}
# - Storage: {user_input['rom']}
# - Camera: {user_input['camera']}
# - Processor: {user_input['processor']}
# - Display: {user_input['display']}
# - Battery: {user_input['battery']}
# - IR Blaster: {user_input['ir']}
# - NFC: {user_input['nfc']}

# Below are the top 3 phones scraped from Flipkart:

# {phones_text}

# For each phone:
# - Rank it (1 to 3)
# - Give reasons why it's suitable
# - Mention any problems or limitations
# - Give an overall short review

# Be clear and user-friendly.
# """

# # ------------------ Routes ------------------ #



def style_gemini_response(raw_result):
    raw_result = raw_result.strip()

    # Fix common Gemini formatting quirks
    raw_result = re.sub(r'\*{2}(.*?)\*{2}', r'<strong>\1</strong>', raw_result)  # **bold**
    raw_result = re.sub(r'\* (.*?)\n', r'<li>\1</li>', raw_result)  # bullet points
    raw_result = re.sub(r'\n\s*\n', r'</ul><br><ul>', raw_result)  # break between bullets
    raw_result = raw_result.replace("<li>", "<ul><li>", 1)  # ensure <ul> starts

    # Specific sections formatting
    replacements = [
        (r'(?i)^Recommendation:', '<h3 class="text-lg font-bold text-indigo-700 mt-4">📌 Recommendation</h3>'),
        (r'(?i)^Analysis.*?:', '<h3 class="text-lg font-bold text-blue-700 mt-4">🧠 Analysis</h3>'),
        (r'(?i)^Ranking.*?:', '<h3 class="text-lg font-bold text-yellow-600 mt-4">📊 Ranking</h3>'),
        (r'(?i)^1\.\s+(.*?):', r'<h4 class="text-md font-semibold text-green-700 mt-3">🥇 \1</h4>'),
        (r'(?i)^2\.\s+(.*?):', r'<h4 class="text-md font-semibold text-yellow-700 mt-3">🥈 \1</h4>'),
        (r'(?i)^3\.\s+(.*?):', r'<h4 class="text-md font-semibold text-red-700 mt-3">🥉 \1</h4>'),
        (r'(?i)overall review\s*:\s*', '<strong class="block text-gray-800 mt-1">⭐ Overall Review:</strong>'),
        (r'(?i)reasons\s*:\s*', '<strong class="block text-green-700">✔️ Reasons:</strong>'),
        (r'(?i)problems/limitations\s*:\s*', '<strong class="block text-red-600">❌ Limitations:</strong>')
    ]

    for pattern, replacement in replacements:
        raw_result = re.sub(pattern, replacement, raw_result, flags=re.MULTILINE)

    # Final wrap-up
    final_html = f"""
    <div class="space-y-2 text-sm leading-relaxed text-gray-800">
        {raw_result}</ul>
    </div>
    """
    return Markup(final_html)
# ... (previous imports remain unchanged)

# ------------------ Helper Functions ------------------ #

def extract_number(text: str, keyword: str) -> int:
    pattern = rf'(\d+)\s*{keyword}'
    match = re.search(pattern, text.lower())
    if match:
        return int(match.group(1))
    return 0

def contains_value_or_higher(text: str, target: str, keyword: str) -> bool:
    try:
        target_value = int(re.findall(r'\d+', target)[0])
        found = extract_number(text, keyword)
        return found >= target_value
    except:
        return False

# ------------------ Scoring ------------------ #

def score_phone(phone: Dict, user_input: Dict) -> float:
    score = 0
    specs_text = " ".join(phone["specs"]).lower()

    if phone["price"] > int(user_input["budget"]):
        return 0  # too expensive

    score += 20  # base score for being in budget

    # RAM / ROM
    if contains_value_or_higher(specs_text, user_input["ram"], "gb"):
        score += 15
    if contains_value_or_higher(specs_text, user_input["rom"], "gb"):
        score += 15

    # Camera
    if contains_value_or_higher(specs_text, user_input["camera"], "mp"):
        score += 10

    # Battery
    if contains_value_or_higher(specs_text, user_input["battery"], "mah"):
        score += 5

    # Display size
    if contains_value_or_higher(specs_text, user_input["display"], "inch"):
        score += 5

    # Processor match
    if user_input["processor"].lower() in specs_text:
        score += 10

    # IR/NFC
    if user_input["ir"] == "yes" and "ir blaster" in specs_text:
        score += 5
    if user_input["nfc"] == "yes" and "nfc" in specs_text:
        score += 5

    # Brand preference
    if user_input["brands"].lower() in phone["title"].lower():
        score += 10

    return score

# ------------------ Prompt Builder ------------------ #

def build_prompt(user_input: Dict, phones: List[Dict], scores: List[float]) -> str:
    phone_lines = []
    for idx, (phone, score) in enumerate(zip(phones, scores), 1):
        phone_lines.append(f"""
{idx}. **{phone['title']}**
   - Score: {score}
   - Price: ₹{phone['price']}
   - Specs: {", ".join(phone['specs'])}
   - URL: {phone['url']}
   - Image: {phone['image']}
""")

    phones_text = "\n".join(phone_lines)

    return f"""
You are a professional smartphone advisor AI. A user is looking for phones with the following preferences:

- Age: {user_input['age']}, Gender: {user_input['gender']}
- Budget: ₹{user_input['budget']}
- Usage: {user_input['usage']}
- Brand Preference: {user_input['brands']}
- RAM: {user_input['ram']}, Storage: {user_input['rom']}
- Camera: {user_input['camera']}, Processor: {user_input['processor']}
- Display: {user_input['display']}, Battery: {user_input['battery']}
- IR Blaster: {user_input['ir']}, NFC: {user_input['nfc']}

Here are the top 3 phones from Flipkart with their AI-calculated scores and specifications:

{phones_text}

Instructions:
- Rank them from 1 to 3 (best to decent)
- Justify rankings using the user’s preferences and specs
- Highlight strengths, limitations, and give a 1-line review for each

Be concise, clear, and helpful.
"""

# ------------------ Main Route (Updated section only) ------------------ #

@app.route('/', methods=['GET', 'POST'])
def index():
    result = ""
    phones = []

    if request.method == 'POST':
        form = request.form
        user_input = {
            'age': form['age'],
            'gender': form['gender'],
            'budget': form['budget'],
            'usage': form['usage'],
            'brands': form['brands'],
            'ram': form['ram'],
            'rom': form['rom'],
            'camera': form['camera'],
            'processor': form['processor'],
            'display': form['display'],
            'battery': form['battery'],
            'ir': form.get('ir', 'no'),
            'nfc': form.get('nfc', 'no')
        }

        query_parts = [
            f"smartphones under {user_input['budget']}",
            user_input['brands'],
            f"{user_input['ram']} RAM",
            f"{user_input['rom']} ROM",
            user_input['processor'],
            user_input['camera'],
            user_input['display'],
            "IR blaster" if user_input['ir'] == "yes" else "",
            "NFC" if user_input['nfc'] == "yes" else ""
        ]
        query = " ".join(filter(None, query_parts))
        logger.info(f"Generated query: {query}")

        phones = cached_fetch_phones(query)

        if not phones:
            result = "Failed to fetch phone data from Flipkart. Please try again later."
        else:
            scored_phones = [(phone, score_phone(phone, user_input)) for phone in phones]
            scored_phones.sort(key=lambda x: x[1], reverse=True)
            top_phones = [phone for phone, _ in scored_phones[:3]]
            scores = [score for _, score in scored_phones[:3]]

            prompt = build_prompt(user_input, top_phones, scores)

            try:
                raw_result = model.generate_content(prompt).text
                result = style_gemini_response(raw_result)
            except Exception as e:
                logger.error(f"Gemini API call failed: {e}")
                result = "Error generating recommendations. Please try again."

    return render_template('form.html', phones=phones, result=result)

# ------------------ Main ------------------ #
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
