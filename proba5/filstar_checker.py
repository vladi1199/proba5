import os
import re
import json
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


def print_context(text, term, limit=20):
    lower = text.lower()
    term_lower = term.lower()

    positions = []
    start = 0

    while True:
        pos = lower.find(term_lower, start)

        if pos == -1:
            break

        positions.append(pos)
        start = pos + len(term)

    print(f"\nTERM: {term}")
    print(f"OCCURRENCES: {len(positions)}")

    for i, pos in enumerate(positions[:limit], 1):

        context_start = max(0, pos - 1000)
        context_end = min(
            len(text),
            pos + len(term) + 2000
        )

        print()
        print(f"--- OCCURRENCE #{i} AT {pos} ---")
        print(text[context_start:context_end])


def main():

    sku = "946537"

    separator("FILSTAR API SEARCH DEEP DIAGNOSTIC")

    url = f"{BASE_URL}/api/search?term={sku}"

    print(f"\nGET: {url}")

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )
    except Exception as e:
        print(f"REQUEST ERROR: {e}")
        return

    print(f"HTTP STATUS: {response.status_code}")
    print(
        f"CONTENT-TYPE: "
        f"{response.headers.get('Content-Type')}"
    )
    print(
        f"SIZE: {len(response.text):,} bytes"
    )

    if response.status_code != 200:
        print(response.text[:3000])
        return

    html = response.text

    # ---------------------------------------------------------
    # SAVE COMPLETE RESPONSE
    # ---------------------------------------------------------

    path = os.path.join(
        DEBUG_DIR,
        "api_search_946537_full.html"
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:
        f.write(html)

    print(f"\nFULL HTML SAVED: {path}")

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    # ---------------------------------------------------------
    # 1. ALL SCRIPT TAGS
    # ---------------------------------------------------------

    separator("SCRIPT TAGS")

    scripts = soup.find_all("script")

    print(f"TOTAL SCRIPT TAGS: {len(scripts)}")

    interesting_script_count = 0

    interesting_terms = [
        "946537",
        "946534",
        "946535",
        "variant",
        "variants",
        "quantity",
        "stock",
        "barcode",
        "discountedPrice",
        "originalPrice",
        "productId",
        "variantId",
        "sku",
        "stores",
        "store",
        "8617",
        "8618",
    ]

    for i, script in enumerate(scripts, 1):

        script_text = script.get_text()

        if not script_text.strip():
            continue

        lower_script = script_text.lower()

        matches = [
            term
            for term in interesting_terms
            if term.lower() in lower_script
        ]

        if matches:

            interesting_script_count += 1

            print()
            print(
                f"--- SCRIPT #{i} ---"
            )

            print(
                f"TYPE: {script.get('type')}"
            )

            print(
                f"SIZE: {len(script_text):,}"
            )

            print(
                f"MATCHES: {matches}"
            )

            print(
                script_text[:15000]
            )

    print()
    print(
        f"INTERESTING SCRIPTS: "
        f"{interesting_script_count}"
    )

    # ---------------------------------------------------------
    # 2. JSON-LD
    # ---------------------------------------------------------

    separator("JSON-LD")

    jsonld = soup.find_all(
        "script",
        attrs={
            "type": "application/ld+json"
        }
    )

    print(
        f"JSON-LD BLOCKS: {len(jsonld)}"
    )

    for i, block in enumerate(jsonld, 1):

        text = block.get_text(
            strip=True
        )

        print()
        print(
            f"--- JSON-LD #{i} ---"
        )

        print(
            text[:20000]
        )

    # ---------------------------------------------------------
    # 3. ALL DATA ATTRIBUTES CONTAINING SKU / PRODUCT / VARIANT
    # ---------------------------------------------------------

    separator("ALL DATA ATTRIBUTES")

    data_matches = 0

    for tag in soup.find_all(True):

        for key, value in tag.attrs.items():

            if not str(key).lower().startswith("data-"):
                continue

            key_text = str(key)
            value_text = str(value)

            combined = (
                key_text + " " + value_text
            ).lower()

            if any(
                term.lower() in combined
                for term in [
                    "sku",
                    "variant",
                    "product",
                    "quantity",
                    "stock",
                    "barcode",
                    "store",
                    "price",
                    "946537",
                    "8617",
                    "8618",
                ]
            ):

                data_matches += 1

                print()
                print(
                    f"<{tag.name}>"
                )

                print(
                    f"{key_text} = {value_text}"
                )

    print()
    print(
        f"DATA ATTRIBUTE MATCHES: "
        f"{data_matches}"
    )

    # ---------------------------------------------------------
    # 4. EXACT SKU OCCURRENCES IN COMPLETE HTML
    # ---------------------------------------------------------

    separator("EXACT SKU CONTEXT")

    print_context(
        html,
        "946537",
        limit=30
    )

    # ---------------------------------------------------------
    # 5. VARIANT CONTEXT IN COMPLETE HTML
    # ---------------------------------------------------------

    separator("VARIANT CONTEXT")

    print_context(
        html,
        "variant",
        limit=30
    )

    # ---------------------------------------------------------
    # 6. QUANTITY CONTEXT
    # ---------------------------------------------------------

    separator("QUANTITY CONTEXT")

    print_context(
        html,
        "quantity",
        limit=20
    )

    # ---------------------------------------------------------
    # 7. STOCK CONTEXT
    # ---------------------------------------------------------

    separator("STOCK CONTEXT")

    print_context(
        html,
        "stock",
        limit=20
    )

    # ---------------------------------------------------------
    # 8. PRICE CONTEXT
    # ---------------------------------------------------------

    separator("PRICE CONTEXT")

    print_context(
        html,
        "price",
        limit=20
    )

    # ---------------------------------------------------------
    # 9. POSSIBLE JSON OBJECTS
    # ---------------------------------------------------------

    separator("POSSIBLE JSON OBJECTS")

    # Look for obvious JSON-like structures containing
    # variant / SKU / product information.

    patterns = [
        r'\{[^{}]{0,5000}"variant"[^{}]{0,5000}\}',
        r'\{[^{}]{0,5000}"variants"[^{}]{0,5000}\}',
        r'\{[^{}]{0,5000}"sku"[^{}]{0,5000}\}',
        r'\{[^{}]{0,5000}"quantity"[^{}]{0,5000}\}',
        r'\{[^{}]{0,5000}"stock"[^{}]{0,5000}\}',
    ]

    found = set()

    for pattern in patterns:

        matches = re.findall(
            pattern,
            html,
            flags=re.IGNORECASE
        )

        for match in matches:

            clean = match.strip()

            if clean not in found:

                found.add(clean)

                print()
                print(
                    "--- POSSIBLE JSON ---"
                )

                print(
                    clean[:10000]
                )

    print()
    print(
        f"POSSIBLE JSON BLOCKS: "
        f"{len(found)}"
    )

    # ---------------------------------------------------------
    # 10. GLOBAL KEYWORD COUNTS
    # ---------------------------------------------------------

    separator("GLOBAL KEYWORD COUNTS")

    terms = [
        "946537",
        "946534",
        "946535",
        "8617",
        "8618",
        "variant",
        "variants",
        "variantid",
        "productid",
        "sku",
        "barcode",
        "quantity",
        "stock",
        "price",
        "discountedprice",
        "originalprice",
        "stores",
        "store",
        "plovdiv",
        "sofia",
        "defaultvariant",
    ]

    lower_html = html.lower()

    for term in terms:

        count = lower_html.count(
            term.lower()
        )

        print(
            f"{term}: {count}"
        )

    separator("END OF DIAGNOSTIC")


if __name__ == "__main__":
    main()
