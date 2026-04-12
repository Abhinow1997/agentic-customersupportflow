import json
from scrapling.fetchers import StealthyFetcher

def scrape_walmart_product(url: str):
    print(f"Scraping Walmart URL: {url}\n")

    try:
        page = StealthyFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
            timeout=30000
        )

        if page.status != 200:
            print(f"Failed to fetch page. Status code: {page.status}")
            return None

        # ------------------------
        # 1. TITLE
        # ------------------------
        title = (
            page.css("h1 span::text").get()
            or page.css("h1::text").get()
        )

        # ------------------------
        # 2. PRICE
        # ------------------------
        price = (
            page.css('[data-automation-id="product-price"]::text').get()
            or page.css('span[itemprop="price"]::text').get()
            or page.css('span[class*="price"]::text').get()
        )

        # ------------------------
        # 3. RATING (multiple fallbacks)
        # ------------------------
        rating = (
            page.css('[aria-label*="out of 5 stars"]::attr(aria-label)').get()
            or page.css('[itemprop="ratingValue"]::attr(content)').get()
            or page.xpath('//*[contains(text(), "out of 5")]/text()').get()
        )

        # ------------------------
        # 4. FEATURES (JSON FIRST — ALWAYS)
        # ------------------------
        features = []

        try:
            script = page.css('script#__NEXT_DATA__::text').get()
            if script:
                data = json.loads(script)
                product = data["props"]["pageProps"]["initialData"]["data"]["product"]

                # JSON fields Walmart uses
                features = (
                    product.get("highlights")
                    or product.get("shortDescription")
                    or []
                )

                # Convert string → list
                if isinstance(features, str):
                    features = [features]

        except Exception:
            pass

        # ------------------------
        # 5. HTML fallback (only if JSON missing)
        # ------------------------
        if not features:
            features = page.xpath(
                '//h2[contains(text(), "Key item features")]/following-sibling::ul[1]/li//text()'
            ).getall()

        if not features:
            features = page.xpath(
                '//h2[contains(text(), "About this item")]/following-sibling::ul[1]/li//text()'
            ).getall()

        # Clean
        features = [f.strip() for f in features if f.strip()]
        features = features[:10]

        # ------------------------
        # FINAL OUTPUT
        # ------------------------
        product_data = {
            "url": url,
            "title": title.strip() if title else "Title not found",
            "price": price.strip() if price else "Price not found",
            "rating": rating.strip() if rating else "Rating not found",
            "features": features if features else ["No features found"]
        }

        return product_data

    except Exception as e:
        print(f"An error occurred during scraping: {e}")
        return None


# ------------------------
# RUN SCRIPT
# ------------------------
if __name__ == "__main__":
    target_url = "https://www.walmart.com/ip/KONG-Dr-Noys-Plush-Frog-Squeaker-Dog-Toy/19629165"

    data = scrape_walmart_product(target_url)

    if data:
        print("Scrape Successful:\n")
        print(json.dumps(data, indent=4))