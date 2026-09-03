import os
import re
import json
import html
import csv
import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIG
# ============================================================

BASE_URL = "https://filstar.com"
CSV_FILE = "sku_list_filstar.csv"
DEBUG_DIR = "debug_html"

TEST_SKUS = [
    "946537",
    "946534",
    "946535",
]

WAIT = 2

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "bg-BG,bg;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}


# ============================================================
# DEBUG DIRECTORY
# ============================================================

def prepare_debug_folder():
    os.makedirs(DEBUG_DIR, exist_ok=True)


# ============================================================
# SAVE TEXT
# ============================================================

def save_text(filename, content):
    path = os.path.join(DEBUG_DIR, filename)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return path


# ============================================================
# API SEARCH
# ============================================================

def api_search(session, term, filename_prefix):
    """
    Единствено /api/search се използва в този тест.
    """

    url = f"{BASE_URL}/api/search"

    try:
        response = session.get(
            url,
            params={"term": term},
            headers=HEADERS,
            timeout=30
        )

    except Exception as e:

        print(f"   ❌ ERROR: {e}")

        return None

    print(
        f"   🔎 /api/search?term={term}"
        f" → HTTP {response.status_code}"
    )

    print(
        f"   Content-Type: "
        f"{response.headers.get('Content-Type', '')}"
    )

    print(
        f"   Размер: "
        f"{len(response.content):,} bytes"
    )

    path = save_text(
        f"{filename_prefix}.html",
        response.text
    )

    print(
        f"   💾 Raw HTML: {path}"
    )

    return response.text


# ============================================================
# EXTRACT PRODUCT CONTAINERS
# ============================================================

def find_product_containers(source):

    pattern = re.compile(
        r'<div\b[^>]*class\s*=\s*["\'][^"\']*'
        r'product-item-wapper[^"\']*["\'][^>]*>',
        re.I
    )

    containers = []

    for match in pattern.finditer(source):

        start = match.start()

        depth = 0

        tag_pattern = re.compile(
            r"</?div\b[^>]*>",
            re.I
        )

        for tag_match in tag_pattern.finditer(
            source,
            start
        ):

            tag = tag_match.group(0)

            if re.match(
                r"<div\b",
                tag,
                re.I
            ):
                depth += 1

            elif re.match(
                r"</div",
                tag,
                re.I
            ):
                depth -= 1

                if depth == 0:

                    end = tag_match.end()

                    containers.append(
                        source[start:end]
                    )

                    break

    return containers


# ============================================================
# EXTRACT DATA ATTRIBUTES
# ============================================================

def extract_data_attributes(container):

    attributes = {}

    matches = re.findall(
        r'(data-[a-zA-Z0-9:_-]+)\s*=\s*["\']([^"\']*)["\']',
        container,
        re.I
    )

    for key, value in matches:

        attributes[key] = html.unescape(value)

    return attributes


# ============================================================
# PRODUCT CONTAINER SUMMARY
# ============================================================

def analyze_containers(source, label):

    print()
    print("=" * 70)
    print(f"PRODUCT CONTAINERS: {label}")
    print("=" * 70)

    containers = find_product_containers(source)

    print(
        f"Product containers: {len(containers)}"
    )

    summary = []

    for index, container in enumerate(
        containers,
        start=1
    ):

        print()
        print(
            f"Container #{index}"
        )

        print(
            f"Size: {len(container):,} bytes"
        )

        attrs = extract_data_attributes(
            container
        )

        print(
            f"Product ID: "
            f"{attrs.get('data-product-id', 'N/A')}"
        )

        print(
            f"Product name: "
            f"{attrs.get('data-product-name', 'N/A')}"
        )

        print(
            f"Product variant: "
            f"{attrs.get('data-product-variant', 'N/A')}"
        )

        print(
            f"Brand: "
            f"{attrs.get('data-product-brand', 'N/A')}"
        )

        print(
            f"Category: "
            f"{attrs.get('data-product-category', 'N/A')}"
        )

        hrefs = re.findall(
            r'href\s*=\s*["\']([^"\']+)["\']',
            container,
            re.I
        )

        print(
            f"HREFs: {hrefs[:10]}"
        )

        # Save each container
        save_text(
            f"{label}_container_{index}.html",
            container
        )

        summary.append({
            "number": index,
            "size": len(container),
            "data_attributes": attrs,
            "hrefs": hrefs,
            "html": container
        })

    return summary


# ============================================================
# SEARCH FOR EXACT TERM
# ============================================================

def exact_occurrences(source, term):

    positions = []

    start = 0

    while True:

        position = source.find(
            term,
            start
        )

        if position == -1:
            break

        positions.append(position)

        start = position + len(term)

    return positions


# ============================================================
# CONTEXT AROUND TERM
# ============================================================

def get_contexts(source, term, radius=1500):

    positions = exact_occurrences(
        source,
        term
    )

    contexts = []

    for index, position in enumerate(
        positions,
        start=1
    ):

        start = max(
            0,
            position - radius
        )

        end = min(
            len(source),
            position + len(term) + radius
        )

        contexts.append({
            "number": index,
            "position": position,
            "context": source[start:end]
        })

    return contexts


# ============================================================
# TERM ANALYSIS
# ============================================================

def analyze_term(source, term, label):

    positions = exact_occurrences(
        source,
        term
    )

    print(
        f"   {term}: "
        f"{len(positions)} occurrence(s)"
    )

    contexts = get_contexts(
        source,
        term
    )

    output = []

    for item in contexts:

        output.append(
            "=" * 100
        )

        output.append(
            f"OCCURRENCE #{item['number']}"
        )

        output.append(
            f"Position: {item['position']}"
        )

        output.append(
            item["context"]
        )

        output.append("")

    save_text(
        f"{label}_{term}_contexts.txt",
        "\n".join(output)
    )

    return len(positions)


# ============================================================
# EXTRACT PRODUCT IDS
# ============================================================

def extract_product_ids(source):

    ids = re.findall(
        r'data-product-id\s*=\s*["\']([^"\']+)["\']',
        source,
        re.I
    )

    unique = []

    for value in ids:

        if value not in unique:
            unique.append(value)

    return unique


# ============================================================
# EXTRACT PRODUCT NAMES
# ============================================================

def extract_product_names(source):

    names = re.findall(
        r'data-product-name\s*=\s*["\']([^"\']*)["\']',
        source,
        re.I
    )

    unique = []

    for value in names:

        value = html.unescape(value)

        if value not in unique:
            unique.append(value)

    return unique


# ============================================================
# EXTRACT HREFS
# ============================================================

def extract_hrefs(source):

    hrefs = re.findall(
        r'href\s*=\s*["\']([^"\']+)["\']',
        source,
        re.I
    )

    unique = []

    for href in hrefs:

        if href not in unique:
            unique.append(href)

    return unique


# ============================================================
# KEYWORD ANALYSIS
# ============================================================

def keyword_analysis(source, label):

    print()
    print("=" * 70)
    print(f"KEYWORD ANALYSIS: {label}")
    print("=" * 70)

    keywords = [
        "variant",
        "variants",
        "quantity",
        "price",
        "discountedPrice",
        "productId",
        "variantId",
        "sku",
        "barcode",
        "stores",
        "defaultVariant",
        "add-variant-to-cart",
        "search-autocomplete",
        "search-json-typesense",
        "serialize",
        "946537",
        "946534",
        "946535",
        "2557",
    ]

    result = {}

    lower_source = source.lower()

    for keyword in keywords:

        count = lower_source.count(
            keyword.lower()
        )

        result[keyword] = count

        print(
            f"   {keyword}: {count}"
        )

    save_text(
        f"{label}_keywords.json",
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        )
    )

    return result


# ============================================================
# SEARCH RESULT SUMMARY
# ============================================================

def create_summary(source, label):

    product_ids = extract_product_ids(
        source
    )

    product_names = extract_product_names(
        source
    )

    hrefs = extract_hrefs(
        source
    )

    summary = {
        "label": label,
        "size": len(source),
        "product_ids": product_ids,
        "product_names": product_names,
        "hrefs": hrefs,
        "exact_terms": {
            "946537": len(
                exact_occurrences(
                    source,
                    "946537"
                )
            ),
            "946534": len(
                exact_occurrences(
                    source,
                    "946534"
                )
            ),
            "946535": len(
                exact_occurrences(
                    source,
                    "946535"
                )
            ),
            "2557": len(
                exact_occurrences(
                    source,
                    "2557"
                )
            )
        }
    }

    save_text(
        f"{label}_summary.json",
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2
        )
    )

    return summary


# ============================================================
# RUN ONE TEST
# ============================================================

def run_test(
    session,
    term,
    label
):

    print()
    print("=" * 70)
    print(f"TEST: {label}")
    print(
        f"TERM: {term}"
    )
    print("=" * 70)

    source = api_search(
        session,
        term,
        label
    )

    if source is None:
        return

    # --------------------------------------------------------
    # BASIC SUMMARY
    # --------------------------------------------------------

    summary = create_summary(
        source,
        label
    )

    print()
    print(
        "Product IDs:"
    )

    if summary["product_ids"]:

        for value in summary["product_ids"]:
            print(
                f"   {value}"
            )

    else:

        print(
            "   няма"
        )

    print()
    print(
        "Product names:"
    )

    if summary["product_names"]:

        for value in summary["product_names"]:

            print(
                f"   {value}"
            )

    else:

        print(
            "   няма"
        )

    # --------------------------------------------------------
    # PRODUCT CONTAINERS
    # --------------------------------------------------------

    containers = analyze_containers(
        source,
        label
    )

    # --------------------------------------------------------
    # IMPORTANT TERMS
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(f"EXACT TERM ANALYSIS: {label}")
    print("=" * 70)

    terms = [
        "946537",
        "946534",
        "946535",
        "2557",
        "Комплект мухи за булдо FilStar тип C",
    ]

    for test_term in terms:

        analyze_term(
            source,
            test_term,
            label
        )

    # --------------------------------------------------------
    # KEYWORDS
    # --------------------------------------------------------

    keyword_analysis(
        source,
        label
    )

    # --------------------------------------------------------
    # HREFS
    # --------------------------------------------------------

    hrefs = extract_hrefs(
        source
    )

    product_hrefs = [
        href
        for href in hrefs
        if (
            href.startswith("/")
            and href not in [
                "/",
                "/search"
            ]
        )
    ]

    save_text(
        f"{label}_hrefs.txt",
        "\n".join(
            product_hrefs
        )
    )

    print()
    print(
        f"Internal HREFs saved: "
        f"{len(product_hrefs)}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    prepare_debug_folder()

    print("=" * 70)
    print("FILSTAR /api/search PRODUCT RELATION DIAGNOSTIC")
    print("=" * 70)

    print()
    print(
        "Този тест използва САМО:"
    )

    print(
        "   /api/search"
    )

    print()
    print(
        "НЕ се използват:"
    )

    print(
        "   - /search"
    )

    print(
        "   - /get-serialize-product/"
    )

    print(
        "   - /search-json-typesense"
    )

    print(
        "   - product page"
    )

    print(
        "   - browser automation"
    )

    print(
        "   - Cloudflare bypass"
    )

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    # ========================================================
    # TEST 1 — SKU 946537
    # ========================================================

    run_test(
        session,
        "946537",
        "api_sku_946537"
    )

    # ========================================================
    # TEST 2 — SKU 946534
    # ========================================================

    run_test(
        session,
        "946534",
        "api_sku_946534"
    )

    # ========================================================
    # TEST 3 — SKU 946535
    # ========================================================

    run_test(
        session,
        "946535",
        "api_sku_946535"
    )

    # ========================================================
    # TEST 4 — PRODUCT ID
    # ========================================================

    run_test(
        session,
        "2557",
        "api_product_2557"
    )

    # ========================================================
    # TEST 5 — PRODUCT NAME
    # ========================================================

    run_test(
        session,
        "Комплект мухи за булдо FilStar тип C",
        "api_product_name"
    )

    # ========================================================
    # FINISHED
    # ========================================================

    print()
    print("=" * 70)
    print("DIAGNOSTIC FINISHED")
    print("=" * 70)

    print()
    print(
        f"Debug folder: {DEBUG_DIR}"
    )

    print()
    print(
        "Създадени са отделни резултати за:"
    )

    print(
        "   1. SKU 946537"
    )

    print(
        "   2. SKU 946534"
    )

    print(
        "   3. SKU 946535"
    )

    print(
        "   4. Product ID 2557"
    )

    print(
        "   5. Името на продукта"
    )


if __name__ == "__main__":
    main()
