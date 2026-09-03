import os
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://filstar.com"
DEBUG_DIR = "debug_html"

os.makedirs(DEBUG_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "bg-BG,bg;q=0.9,en-US;q=0.8,en;q=0.7",
}


def separator(title):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def request(method, url, **kwargs):

    print(f"\n{method.upper()} {url}")

    try:
        response = requests.request(
            method,
            url,
            headers=HEADERS,
            timeout=30,
            **kwargs
        )

        print(f"STATUS: {response.status_code}")
        print(
            f"CONTENT-TYPE: "
            f"{response.headers.get('Content-Type')}"
        )
        print(
            f"SIZE: "
            f"{len(response.text):,} bytes"
        )

        return response

    except Exception as e:

        print(f"ERROR: {e}")
        return None


def analyze_response(response, label):

    if response is None:
        return

    separator(f"ANALYSIS: {label}")

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    containers = soup.select(
        ".product-item-wapper"
    )

    print(
        f"PRODUCT CONTAINERS: "
        f"{len(containers)}"
    )

    for index, container in enumerate(
        containers,
        start=1
    ):

        print()
        print(
            f"--- PRODUCT #{index} ---"
        )

        attrs = container.attrs

        for key, value in attrs.items():

            if (
                key.startswith("data-")
                or key == "class"
            ):
                print(
                    f"{key} = {value}"
                )

        text = container.get_text(
            " ",
            strip=True
        )

        print(
            f"TEXT: {text[:500]}"
        )

        print(
            f"HTML SIZE: "
            f"{len(str(container)):,}"
        )

    # Търсим конкретните SKU-та навсякъде
    terms = [
        "946537",
        "946534",
        "946535",
        "2557",
    ]

    print()
    print("--- EXACT TERM COUNTS ---")

    for term in terms:

        count = response.text.count(term)

        print(
            f"{term}: {count}"
        )

    # Търсим възможни JSON / variant ключове
    terms = [
        "variant",
        "variants",
        "variantId",
        "productId",
        "product_id",
        "sku",
        "barcode",
        "quantity",
        "stock",
        "price",
        "discountedPrice",
        "originalPrice",
        "stores",
        "store",
    ]

    print()
    print("--- KEYWORD COUNTS ---")

    lower = response.text.lower()

    for term in terms:

        count = lower.count(
            term.lower()
        )

        if count:
            print(
                f"{term}: {count}"
            )


def save_response(response, filename):

    if response is None:
        return

    path = os.path.join(
        DEBUG_DIR,
        filename
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            response.text
        )

    print(
        f"Saved: {path}"
    )


def main():

    sku = "946537"
    product_id = "2557"

    separator(
        "FILSTAR /api/search PARAMETER TEST"
    )

    # --------------------------------------------------
    # 1. Стандартен GET
    # --------------------------------------------------

    response = request(
        "GET",
        f"{BASE_URL}/api/search",
        params={
            "term": sku
        }
    )

    analyze_response(
        response,
        "GET term=946537"
    )

    save_response(
        response,
        "api_test_01_term.html"
    )

    # --------------------------------------------------
    # 2. GET с page
    # --------------------------------------------------

    response = request(
        "GET",
        f"{BASE_URL}/api/search",
        params={
            "term": sku,
            "page": 1
        }
    )

    analyze_response(
        response,
        "GET term + page=1"
    )

    # --------------------------------------------------
    # 3. GET с limit
    # --------------------------------------------------

    response = request(
        "GET",
        f"{BASE_URL}/api/search",
        params={
            "term": sku,
            "limit": 100
        }
    )

    analyze_response(
        response,
        "GET term + limit=100"
    )

    # --------------------------------------------------
    # 4. GET с per_page
    # --------------------------------------------------

    response = request(
        "GET",
        f"{BASE_URL}/api/search",
        params={
            "term": sku,
            "per_page": 100
        }
    )

    analyze_response(
        response,
        "GET term + per_page=100"
    )

    # --------------------------------------------------
    # 5. GET с product
    # --------------------------------------------------

    response = request(
        "GET",
        f"{BASE_URL}/api/search",
        params={
            "term": sku,
            "product": product_id
        }
    )

    analyze_response(
        response,
        "GET term + product=2557"
    )

    # --------------------------------------------------
    # 6. GET с product_id
    # --------------------------------------------------

    response = request(
        "GET",
        f"{BASE_URL}/api/search",
        params={
            "term": sku,
            "product_id": product_id
        }
    )

    analyze_response(
        response,
        "GET term + product_id=2557"
    )

    # --------------------------------------------------
    # 7. GET с variant
    # --------------------------------------------------

    response = request(
        "GET",
        f"{BASE_URL}/api/search",
        params={
            "term": sku,
            "variant": sku
        }
    )

    analyze_response(
        response,
        "GET term + variant=946537"
    )

    # --------------------------------------------------
    # 8. GET с sku
    # --------------------------------------------------

    response = request(
        "GET",
        f"{BASE_URL}/api/search",
        params={
            "term": sku,
            "sku": sku
        }
    )

    analyze_response(
        response,
        "GET term + sku=946537"
    )

    # --------------------------------------------------
    # 9. GET само SKU параметър
    # --------------------------------------------------

    response = request(
        "GET",
        f"{BASE_URL}/api/search",
        params={
            "sku": sku
        }
    )

    analyze_response(
        response,
        "GET sku=946537"
    )

    # --------------------------------------------------
    # 10. GET само product_id
    # --------------------------------------------------

    response = request(
        "GET",
        f"{BASE_URL}/api/search",
        params={
            "product_id": product_id
        }
    )

    analyze_response(
        response,
        "GET product_id=2557"
    )

    # --------------------------------------------------
    # 11. POST form
    # --------------------------------------------------

    response = request(
        "POST",
        f"{BASE_URL}/api/search",
        data={
            "term": sku
        }
    )

    analyze_response(
        response,
        "POST form term=946537"
    )

    # --------------------------------------------------
    # 12. POST JSON
    # --------------------------------------------------

    response = request(
        "POST",
        f"{BASE_URL}/api/search",
        json={
            "term": sku
        }
    )

    analyze_response(
        response,
        "POST JSON term=946537"
    )

    separator(
        "END OF PARAMETER TEST"
    )

    print(
        """
Тестирахме:

1. term
2. page
3. limit
4. per_page
5. product
6. product_id
7. variant
8. sku
9. само sku
10. само product_id
11. POST form
12. POST JSON

Търсим дали някой от вариантите ще върне различен
HTML или конкретните данни за SKU 946537.
"""
    )


if __name__ == "__main__":
    main()
