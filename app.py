import requests
from bs4 import BeautifulSoup

# # URL of the Flipkart page you want to scrape
# url = "https://www.flipkart.com/search?q=fridege"

# # Set up headers to mimic a browser request
# headers = {
#     "User-Agent": "Mozilla/5.0"
# }

# # Send a GET request to the page
# response = requests.get(url, headers=headers)

# # Check if the request was successful
# if response.status_code == 200:
#     soup = BeautifulSoup(response.text, "html.parser")

#     # Extracting all product containers
#     product_containers = soup.find_all("div", {"class": "tUxRFH"})

#     # Extract details from each product container
#     for product in product_containers:
#         # Extract product link
#         product_link = product.find("a", {"class": "CGtC98"})["href"] if product.find("a", {"class": "CGtC98"}) else "No Link"

#         # Extract product image
#         product_image = product.find("img", {"class": "DByuf4"})["src"] if product.find("img", {"class": "DByuf4"}) else "No Image"

#         # Extract product title
#         product_title = product.find("div", {"class": "KzDlHZ"}).get_text() if product.find("div", {"class": "KzDlHZ"}) else "No Title"

#         # Extract product price
#         product_price = product.find("div", {"class": "Nx9bqj"}).get_text() if product.find("div", {"class": "Nx9bqj"}) else "No Price"

#         # Extract product discount
#         product_discount = product.find("div", {"class": "UkUFwK"}).get_text() if product.find("div", {"class": "UkUFwK"}) else "No Discount"

#         # Extract product ratings and reviews
#         product_rating = product.find("span", {"class": "Y1HWO0"}).get_text() if product.find("span", {"class": "Y1HWO0"}) else "No Rating"
#         product_reviews = product.find("span", {"class": "hG7V+4"}).get_text() if product.find("span", {"class": "hG7V+4"}) else "No Reviews"

#         # Extract specifications
#         product_specs = product.find("ul", {"class": "G4BRas"})
#         specs_list = [li.get_text() for li in product_specs.find_all("li")] if product_specs else ["No Specifications"]

#         # Print the extracted details
#         print("Product Title:", product_title)
#         print("Product Link:", "https://www.flipkart.com" + product_link)
#         print("Product Image:", product_image)
#         print("Product Price:", product_price)
#         print("Product Discount:", product_discount)
#         print("Product Rating:", product_rating)
#         print("Product Reviews:", product_reviews)
#         print("Specifications:")
#         for spec in specs_list:
#             print(f"  - {spec}")
#         print("-" * 40)
# else:
#     print("Failed to fetch page.")
def fetch_products_from_flipkart(query: str, max_products: int = 20) -> List[Dict]:
    url = f"https://www.flipkart.com/search?q={query.replace(' ', '+')}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    try:
        logger.info(f"Fetching URL: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            logger.error(f"Failed to fetch page: Status {response.status_code}")
            return []

        soup = bs(response.text, "html.parser")
        product_containers = soup.find_all("div", {"class": "tUxRFH"})

        product_data = []
        seen_titles = set()

        for product in product_containers:
            title = product.find("div", {"class": "KzDlHZ"}).get_text() if product.find("div", {"class": "KzDlHZ"}) else "N/A"
            if title in seen_titles:
                continue
            seen_titles.add(title)

            product_link = product.find("a", {"class": "CGtC98"})["href"] if product.find("a", {"class": "CGtC98"}) else ""
            full_link = f"https://www.flipkart.com{product_link}" if product_link else ""

            product_image = product.find("img", {"class": "DByuf4"})["src"] if product.find("img", {"class": "DByuf4"}) else ""

            price = 0
            price_tag = product.find("div", {"class": "Nx9bqj"}) or product.find("div", {"class": "_30jeq3"})
            if price_tag:
                try:
                    price = int(price_tag.text.replace('₹', '').replace(',', '').strip())
                except:
                    pass

            discount = product.find("div", {"class": "UkUFwK"}).get_text() if product.find("div", {"class": "UkUFwK"}) else "No Discount"
            rating = product.find("span", {"class": "Y1HWO0"}).get_text() if product.find("span", {"class": "Y1HWO0"}) else "No Rating"
            reviews = product.find("span", {"class": "hG7V+4"}).get_text() if product.find("span", {"class": "hG7V+4"}) else "No Reviews"

            specs_list = []
            product_specs = product.find("ul", {"class": "G4BRas"})
            if product_specs:
                specs_list = [li.get_text(strip=True) for li in product_specs.find_all("li") if li.get_text(strip=True)]

            product_data.append({
                "title": title,
                "price": price,
                "specs": specs_list,
                "url": full_link,
                "image": product_image,
                "discount": discount,
                "rating": rating,
                "reviews": reviews
            })

            if len(product_data) >= max_products:
                break

        return product_data

    except Exception as e:
        logger.error(f"Scraping error: {e}")
        return []