from flask import Flask, render_template, request, jsonify
from bs4 import BeautifulSoup
import requests
import google.generativeai as genai
import os
import re
from dotenv import load_dotenv
load_dotenv()
app = Flask(__name__)

# Configure Gemini API
genai.configure(api_key=os.getenv("API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')


def preprocess_markdown(text):
    # Bold **text**
    text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)

    # Headers: #, ##, ### to h1, h2, h3
    text = re.sub(r"### (.*)", r"<h3>\1</h3>", text)
    text = re.sub(r"## (.*)", r"<h2>\1</h2>", text)
    text = re.sub(r"# (.*)", r"<h1>\1</h1>", text)

    # Bullet points: - item or * item
    text = re.sub(r"(?m)^[\-\*] (.*)", r"<li>\1</li>", text)
    if "<li>" in text:
        text = "<ul>" + text + "</ul>"

    # Numbered lists: 1. Item
    text = re.sub(r"(?m)^\d+\.\s(.*)", r"<li>\1</li>", text)
    if re.search(r"<li>.*</li>", text):
        text = "<ol>" + text + "</ol>"

    # Line breaks
    text = text.replace("\n", "<br>")

    return text

def scrape_flipkart_products(query):
    url = f"https://www.flipkart.com/search?q={query}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    # Category-based scraping logic
    query_lower = query.lower()
    products_data = []

    # 📱📺 Electronics style cards
    if any(keyword in query_lower for keyword in ["phone", "laptop", "tv", "fridge", "fan", "camera", "headphone", "monitor"]):
        product_containers = soup.find_all("div", class_="tUxRFH")
        for product in product_containers:
            product_link = product.find("a", class_="CGtC98")
            product_image = product.find("img", class_="DByuf4")
            product_title = product.find("div", class_="KzDlHZ")
            product_price = product.find("div", class_="Nx9bqj")
            product_discount = product.find("div", class_="UkUFwK")
            product_rating = product.find("span", class_="Y1HWO0")
            product_reviews = product.find("span", class_="hG7V+4")
            product_specs = product.find("ul", class_="G4BRas")

            products_data.append({
                "title": product_title.get_text(strip=True) if product_title else "No Title",
                "link": "https://www.flipkart.com" + product_link["href"] if product_link else "No Link",
                "image": product_image["src"] if product_image else "No Image",
                "price": product_price.get_text(strip=True) if product_price else "No Price",
                "discount": product_discount.get_text(strip=True) if product_discount else "No Discount",
                "rating": product_rating.get_text(strip=True) if product_rating else "No Rating",
                "reviews": product_reviews.get_text(strip=True) if product_reviews else "No Reviews",
                "specifications": [li.get_text(strip=True) for li in product_specs.find_all("li")] if product_specs else []
            })

    # 👗👚 Fashion category (like dresses, shirts, sarees)
    elif any(keyword in query_lower for keyword in ["dress", "shirt", "jeans", "kurti", "saree", "clothing", "tshirt", "top"]):
        product_containers = soup.find_all("div", class_="_1sdMkc")
        for product in product_containers:
            product_link = product.find("a", class_="rPDeLR")
            product_image = product.find("img", class_="_53J4C-")
            product_title = product.find("a", class_="WKTcLC")
            product_brand = product.find("div", class_="syl9yP")
            product_price = product.find("div", class_="Nx9bqj")
            product_discount = product.find("div", class_="UkUFwK")
            product_sizes = product.find("div", class_="OCRRMR")

            products_data.append({
                "title": product_title.get_text(strip=True) if product_title else "No Title",
                "brand": product_brand.get_text(strip=True) if product_brand else "No Brand",
                "link": "https://www.flipkart.com" + product_link["href"] if product_link else "No Link",
                "image": product_image["src"] if product_image else "No Image",
                "price": product_price.get_text(strip=True) if product_price else "No Price",
                "discount": product_discount.get_text(strip=True) if product_discount else "No Discount",
                "rating": "N/A",
                "reviews": "N/A",
                "specifications": [product_sizes.get_text(strip=True).replace("Size", "").strip()] if product_sizes else []
            })

    # 🪑 Furniture or other (fallback)
    else:
        product_containers = soup.find_all("div", class_="tUxRFH") or soup.find_all("div", class_="_1sdMkc")
        for product in product_containers:
            title = product.find("div", class_="KzDlHZ") or product.find("a", class_="WKTcLC")
            image = product.find("img")
            price = product.find("div", class_="Nx9bqj")
            link = product.find("a", href=True)

            products_data.append({
                "title": title.get_text(strip=True) if title else "No Title",
                "image": image["src"] if image else "No Image",
                "link": "https://www.flipkart.com" + link["href"] if link else "No Link",
                "price": price.get_text(strip=True) if price else "No Price",
                "rating": "N/A",
                "discount": "N/A",
                "reviews": "N/A",
                "specifications": []
            })

    return products_data


@app.route("/", methods=["GET", "POST"])
def index():
    query = request.form.get("query") if request.method == "POST" else "smartphone"
    products = scrape_flipkart_products(query)
    return render_template("index.html", products=products, query=query)
@app.route("/recommend", methods=["POST"])
def recommend():
    data = request.json
    products = data["products"]
    preference = data.get("preference", "Recommend the best products overall.")

    prompt = (
    f"You are an expert Flipkart product recommender. The user says: '{preference}'\n\n"
    "Here are some products scraped from Flipkart:\n\n"
    + "\n\n".join([
        f"Product: {p['title']}\nPrice: {p['price']}\nRating: {p['rating']}\nSpecs: {', '.join(p['specifications'])}\nLink: {p['link']}"
        for p in products
    ]) +
    "\n\nRecommend the top 3 products that match the user's preference with clear reasoning.\n"
    "Output can use markdown for formatting."
)


    response = model.generate_content(prompt)
    raw_text = response.text.strip()
    cleaned_html = preprocess_markdown(raw_text)

    return jsonify({"recommendation": cleaned_html})


if __name__ == "__main__":
    app.run(debug=True)
