import os
import re
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
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "bg-BG,bg;q=0.9,en-US;q=0.8,en;q=0.7",
}


def separator(title):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def request_page(url):

    print(f"\nGET: {url}")

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        print(f"HTTP STATUS: {response.status_code}")
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
        print(f"REQUEST ERROR: {e}")
        return None


def save_html(response, filename):

    path = os.path.join(
        DEBUG_DIR,
        filename
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:
        f.write(response.text)

    print(f"DEBUG FILE SAVED: {path}")


def find_terms(text):

    terms = [
        "946537",
        "946534",
        "946535",
        "2557",

        "variant",
        "variants",
        "variantId",
        "variant-id",

        "productId",
        "product-id",

        "sku",
        "barcode",

        "quantity",
        "stock",
        "availability",

        "price",
        "discountedPrice",
        "originalPrice",

        "stores",
        "store",

        "Пловдив",
        "София",

        "Има 6 разновидности",
    ]

    lower = text.lower()

    for term in terms:

        count = lower.count(
            term.lower()
        )

        if count:
            print(
                f"{term}: {count}"
            )


def show_contexts(text):

    separator(
        "IMPORTANT TERM CONTEXT"
    )

    terms = [
        "946537",
        "946534",
        "946535",
        "variant",
        "variants",
        "variantId",
        "productId",
        "sku",
        "barcode",
        "quantity",
        "stock",
        "availability",
        "discountedPrice",
    ]

    lower = text.lower()

    shown = set()

    for term in terms:

        start = 0

        while True:

            position = lower.find(
                term.lower(),
                start
            )

            if position == -1:
                break

            # Не показваме един и същ контекст
            # многократно.
            context_start = max(
                0,
                position - 500
            )

            context_end = min(
                len(text),
                position + len(term) + 1000
            )

            context = text[
                context_start:context_end
            ]

            key = (
                term,
                context_start
            )

            if key not in shown:

                print()
                print(
                    f"--- {term} "
                    f"at {position} ---"
                )

                print(context)

                shown.add(key)

            start = position + len(term)

            # Ограничаваме броя контексти,
            # за да не получим огромен log.
            if len(shown) >= 30:
                return


def inspect_scripts(soup):

    separator(
        "INLINE SCRIPT ANALYSIS"
    )

    scripts = soup.find_all(
        "script"
    )

    print(
        f"TOTAL SCRIPT TAGS: "
        f"{len(scripts)}"
    )

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
        "stock",
        "price",
        "discountedPrice",
        "stores",
    ]

    for index, script in enumerate(
        scripts,
        start=1
    ):

        content = script.get_text(
            "",
            strip=False
        )

        if not content:
            continue

        matches = []

        for term in terms:

            if term.lower() in content.lower():
                matches.append(term)

        if not matches:
            continue

        print()
        print(
            f"SCRIPT #{index}"
        )
        print(
            f"SIZE: {len(content):,}"
        )
        print(
            f"MATCHES: {matches}"
        )

        # Ако е малък inline script,
        # показваме целия.
        if len(content) <= 15000:

            print(
                "--- SCRIPT CONTENT ---"
            )

            print(content)

        else:

            print(
                "--- FIRST 5000 CHARACTERS ---"
            )

            print(
                content[:5000]
            )


def inspect_elements(soup):

    separator(
        "ELEMENT / ATTRIBUTE ANALYSIS"
    )

    interesting = []

    for tag in soup.find_all(True):

        attrs = tag.attrs

        for key, value in attrs.items():

            key_lower = str(key).lower()

            value_text = str(value)

            value_lower = value_text.lower()

            interesting_terms = [
                "946537",
                "946534",
                "946535",
                "2557",
                "variant",
                "sku",
                "barcode",
                "product",
            ]

            if (
                any(
                    term in key_lower
                    for term in [
                        "data-",
                        "variant",
                        "product",
                        "sku",
                        "barcode",
                    ]
                )
                or any(
                    term in value_lower
                    for term in interesting_terms
                )
            ):

                interesting.append(
                    (
                        tag.name,
                        key,
                        value_text
                    )
                )

    # премахваме дубликати
    unique = []

    for item in interesting:

        if item not in unique:
            unique.append(item)

    for tag_name, key, value in unique:

        print(
            f"<{tag_name}> "
            f"{key} = {value}"
        )


def inspect_product_area(soup):

    separator(
        "PRODUCT PAGE STRUCTURE"
    )

    selectors = [
        ".product-detail",
        ".product-details",
        ".product-page",
        ".product",
        ".variants",
        ".variant",
        ".product-variants",
        "[data-product-id]",
    ]

    found = set()

    for selector in selectors:

        elements = soup.select(
            selector
        )

        if not elements:
            continue

        print()
        print(
            f"SELECTOR: {selector}"
        )
        print(
            f"FOUND: {len(elements)}"
        )

        for index, element in enumerate(
            elements[:10],
            start=1
        ):

            html = str(element)

            key = (
                selector,
                html[:1000]
            )

            if key in found:
                continue

            found.add(key)

            print()
            print(
                f"--- ELEMENT #{index} ---"
            )
            print(
                f"SIZE: {len(html):,}"
            )

            print(
                html[:15000]
            )


def main():

    separator(
        "FILSTAR PRODUCT PAGE TEST"
    )

    url = (
        f"{BASE_URL}"
        f"/Muhi-za-buldo-bz"
    )

    response = request_page(
        url
    )

    if response is None:
        return

    save_html(
        response,
        "product_2557_test.html"
    )

    if response.status_code != 200:

        separator(
            "NON-200 RESPONSE"
        )

        print(
            response.text[:10000]
        )

        return

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    separator(
        "GLOBAL TERM COUNTS"
    )

    find_terms(
        response.text
    )

    inspect_elements(
        soup
    )

    inspect_product_area(
        soup
    )

    inspect_scripts(
        soup
    )

    show_contexts(
        response.text
    )

    separator(
        "END OF TEST"
    )


if __name__ == "__main__":
    main()
