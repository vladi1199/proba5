import os
import re
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://filstar.com"
WAIT = 2

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


def print_separator(title):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def get_html(url):
    print(f"\nGET: {url}")

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        print(f"HTTP STATUS: {response.status_code}")
        print(f"CONTENT-TYPE: {response.headers.get('Content-Type')}")
        print(f"SIZE: {len(response.text):,} bytes")

        return response

    except Exception as e:
        print(f"REQUEST ERROR: {e}")
        return None


def find_product_containers(soup):
    """
    Намира всички елементи, които изглеждат като product-item-wapper.
    """

    containers = []

    # Основният вариант
    containers.extend(
        soup.select(".product-item-wapper")
    )

    # Допълнителна проверка за евентуални изписвания
    if not containers:
        for tag in soup.find_all(True):
            classes = tag.get("class", [])

            if any(
                "product-item" in str(c).lower()
                for c in classes
            ):
                containers.append(tag)

    # Премахване на дубликати
    unique = []

    for item in containers:
        if item not in unique:
            unique.append(item)

    return unique


def analyze_container(container, index):
    print_separator(f"PRODUCT CONTAINER #{index}")

    html = str(container)

    print(f"CONTAINER SIZE: {len(html):,} bytes")

    print("\n--- TAG ---")
    print(container.name)

    print("\n--- ALL ATTRIBUTES ---")

    if container.attrs:
        for key, value in container.attrs.items():
            print(f"{key} = {value}")
    else:
        print("NO ATTRIBUTES")

    print("\n--- CLASS ---")
    print(container.get("class"))

    print("\n--- DATA ATTRIBUTES ---")

    found_data = False

    for key, value in container.attrs.items():
        if str(key).lower().startswith("data-"):
            print(f"{key} = {value}")
            found_data = True

    if not found_data:
        print("NO DATA-* ATTRIBUTES ON CONTAINER")

    print("\n--- LINKS ---")

    links = []

    for a in container.find_all("a", href=True):
        href = a.get("href")
        text = " ".join(a.get_text(" ", strip=True).split())

        links.append((href, text))

    if links:
        for href, text in links:
            print(f"HREF: {href}")
            print(f"TEXT: {text[:300]}")
            print("---")
    else:
        print("NO LINKS")

    print("\n--- IMAGES ---")

    images = container.find_all("img")

    if images:
        for img in images:
            print(f"SRC: {img.get('src')}")
            print(f"ALT: {img.get('alt')}")
            print("---")
    else:
        print("NO IMAGES")

    print("\n--- TEXT CONTENT ---")

    text = container.get_text(
        "\n",
        strip=True
    )

    print(text[:10000])

    print("\n--- IMPORTANT TERMS INSIDE CONTAINER ---")

    terms = [
        "946537",
        "946534",
        "946535",
        "2557",
        "variant",
        "variants",
        "variantId",
        "productId",
        "sku",
        "barcode",
        "quantity",
        "price",
        "discountedPrice",
        "originalPrice",
        "discount",
        "stock",
        "availability",
        "stores",
        "store",
        "plovdiv",
        "sofia",
        "Filstar",
    ]

    lower_html = html.lower()

    for term in terms:
        count = lower_html.count(term.lower())

        if count:
            print(f"{term}: {count}")

    print("\n--- HTML INSIDE CONTAINER ---")

    print(html[:30000])

    if len(html) > 30000:
        print()
        print(
            f"[HTML TRUNCATED: total {len(html):,} bytes]"
        )

    return html


def find_json_like_content(container):
    """
    Търси потенциални JSON / Vue атрибути вътре в product container.
    """

    print_separator("JSON / VUE ATTRIBUTE ANALYSIS")

    found = False

    for tag in container.find_all(True):

        for key, value in tag.attrs.items():

            key_lower = str(key).lower()

            if (
                "json" in key_lower
                or "product" in key_lower
                or "variant" in key_lower
                or "sku" in key_lower
                or "data-" in key_lower
            ):

                print(f"TAG: <{tag.name}>")
                print(f"ATTRIBUTE: {key}")
                print(f"VALUE: {value}")
                print("---")

                found = True

    if not found:
        print("NO RELEVANT JSON/VUE/DATA ATTRIBUTES FOUND")


def search_global_scripts(soup):
    print_separator("SCRIPT ANALYSIS")

    scripts = soup.find_all("script")

    print(f"TOTAL SCRIPT TAGS: {len(scripts)}")

    terms = [
        "946537",
        "946534",
        "946535",
        "2557",
        "variant",
        "variants",
        "quantity",
        "price",
        "product",
        "sku",
        "barcode",
        "stores",
    ]

    for index, script in enumerate(scripts, start=1):

        content = script.string

        if not content:
            content = script.get_text()

        if not content:
            continue

        matches = []

        for term in terms:
            if term.lower() in content.lower():
                matches.append(term)

        if matches:

            print()
            print(f"SCRIPT #{index}")
            print(f"SIZE: {len(content):,}")
            print(f"MATCHES: {matches}")

            # Показваме само ако изглежда като inline script,
            # а не огромен външен JS файл.
            if len(content) <= 20000:
                print("--- SCRIPT CONTENT ---")
                print(content[:20000])
            else:
                print("--- FIRST 5000 CHARACTERS ---")
                print(content[:5000])


def save_debug_file(response, filename):
    path = os.path.join(DEBUG_DIR, filename)

    with open(path, "w", encoding="utf-8") as f:
        f.write(response.text)

    print()
    print(f"DEBUG FILE SAVED: {path}")


def test_api_search():

    sku = "946537"

    url = f"{BASE_URL}/api/search?term={sku}"

    print_separator("TEST /api/search")

    response = get_html(url)

    if response is None:
        return

    if response.status_code != 200:
        print("\nREQUEST FAILED")
        return

    filename = f"next_test_{sku}.html"

    save_debug_file(
        response,
        filename
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    print_separator("GLOBAL PRODUCT CONTAINERS")

    containers = find_product_containers(soup)

    print(
        f"PRODUCT CONTAINERS FOUND: {len(containers)}"
    )

    if not containers:
        print("NO PRODUCT CONTAINERS FOUND")
        return

    target_container = None

    for index, container in enumerate(containers, start=1):

        html = str(container)

        if (
            "946537" in html
            or "2557" in html
            or "Комплект мухи за булдо FilStar тип C" in html
        ):
            target_container = container
            target_index = index
            break

    if target_container is None:
        print(
            "\nCould not identify target container."
        )

        # Ако няма директно съвпадение,
        # анализираме първия.
        target_container = containers[0]
        target_index = 1

    print(
        f"\nTARGET CONTAINER: #{target_index}"
    )

    analyze_container(
        target_container,
        target_index
    )

    find_json_like_content(
        target_container
    )

    search_global_scripts(
        soup
    )

    print_separator("END OF TEST")

    print(
        """
Следващата информация, която ни интересува, е:

1. ALL ATTRIBUTES на product container
2. DATA ATTRIBUTES
3. HTML INSIDE CONTAINER
4. JSON / VUE ATTRIBUTE ANALYSIS
5. SCRIPT ANALYSIS

Особено търсим:
- variant ID
- SKU
- barcode
- quantity
- price
- discountedPrice
- productId
- stores
"""
    )


if __name__ == "__main__":
    test_api_search()
