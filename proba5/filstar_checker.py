import os
import re
import json
import hashlib
import html
import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIG
# ============================================================

BASE_URL = "https://filstar.com"

DEBUG_DIR = "debug_html"

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


TESTS = [
    ("946537", "sku_946537"),
    ("946534", "sku_946534"),
    ("946535", "sku_946535"),
    ("2557", "product_2557"),
    (
        "Комплект мухи за булдо FilStar тип C",
        "product_name"
    ),
]


# ============================================================
# HELPERS
# ============================================================

def save_file(filename, content):

    os.makedirs(DEBUG_DIR, exist_ok=True)

    path = os.path.join(
        DEBUG_DIR,
        filename
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(content)

    return path


def sha256_text(text):

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def normalize_html(source):

    """
    Премахва динамични неща, които могат да пречат
    на сравнението между две заявки.
    """

    normalized = source

    # Премахваме търсените термини от URL/meta местата.
    normalized = re.sub(
        r'term=[^"&<> ]+',
        'term=REMOVED',
        normalized,
        flags=re.I
    )

    # Премахваме nonce стойности.
    normalized = re.sub(
        r'nonce=["\'][^"\']+["\']',
        'nonce="REMOVED"',
        normalized,
        flags=re.I
    )

    # Премахваме whitespace.
    normalized = re.sub(
        r'\s+',
        ' ',
        normalized
    )

    return normalized.strip()


# ============================================================
# API SEARCH
# ============================================================

def api_search(
    session,
    term,
    label
):

    print()
    print("=" * 80)
    print(f"REQUEST: {label}")
    print("=" * 80)

    url = f"{BASE_URL}/api/search"

    try:

        response = session.get(
            url,
            params={
                "term": term
            },
            headers=HEADERS,
            timeout=30
        )

    except Exception as e:

        print(
            f"❌ Request error: {e}"
        )

        return None

    print(
        f"URL: {response.url}"
    )

    print(
        f"HTTP: {response.status_code}"
    )

    print(
        f"Content-Type: "
        f"{response.headers.get('Content-Type', '')}"
    )

    print(
        f"Size: "
        f"{len(response.content):,} bytes"
    )

    raw_hash = sha256_text(
        response.text
    )

    normalized_hash = sha256_text(
        normalize_html(
            response.text
        )
    )

    print(
        f"SHA256 raw: "
        f"{raw_hash}"
    )

    print(
        f"SHA256 normalized: "
        f"{normalized_hash}"
    )

    save_file(
        f"{label}.html",
        response.text
    )

    return {
        "term": term,
        "label": label,
        "status": response.status_code,
        "content_type": response.headers.get(
            "Content-Type",
            ""
        ),
        "size": len(response.content),
        "raw_hash": raw_hash,
        "normalized_hash": normalized_hash,
        "source": response.text,
    }


# ============================================================
# PRODUCT CONTAINERS
# ============================================================

def get_product_containers(source):

    soup = BeautifulSoup(
        source,
        "html.parser"
    )

    containers = soup.select(
        ".product-item-wapper"
    )

    return containers


# ============================================================
# CONTAINER ANALYSIS
# ============================================================

def analyze_container(container):

    result = {}

    for attribute in [
        "data-product-id",
        "data-product-name",
        "data-product-variant",
        "data-product-brand",
        "data-product-category",
    ]:

        result[attribute] = (
            container.get(attribute)
        )

    result["hrefs"] = []

    for a in container.find_all(
        "a",
        href=True
    ):

        href = a.get(
            "href"
        )

        if href not in result["hrefs"]:

            result["hrefs"].append(
                href
            )

    result["images"] = []

    for img in container.find_all(
        "img"
    ):

        for attribute in [
            "src",
            "data-src",
            "data-original",
        ]:

            value = img.get(
                attribute
            )

            if value and value not in result["images"]:

                result["images"].append(
                    value
                )

    result["text"] = " ".join(
        container.stripped_strings
    )

    return result


# ============================================================
# PRODUCT ANALYSIS
# ============================================================

def analyze_products(result):

    source = result["source"]

    containers = get_product_containers(
        source
    )

    print()
    print(
        f"Product containers: "
        f"{len(containers)}"
    )

    products = []

    for index, container in enumerate(
        containers,
        start=1
    ):

        data = analyze_container(
            container
        )

        products.append(
            data
        )

        print()
        print(
            f"--- Container #{index} ---"
        )

        print(
            f"Product ID: "
            f"{data.get('data-product-id')}"
        )

        print(
            f"Product name: "
            f"{data.get('data-product-name')}"
        )

        print(
            f"Variant: "
            f"{data.get('data-product-variant')}"
        )

        print(
            f"Brand: "
            f"{data.get('data-product-brand')}"
        )

        print(
            f"Category: "
            f"{data.get('data-product-category')}"
        )

        print(
            f"HREFs: "
            f"{data['hrefs'][:10]}"
        )

        print(
            f"Images: "
            f"{data['images'][:5]}"
        )

        print(
            f"Text: "
            f"{data['text'][:500]}"
        )

        save_file(
            (
                f"{result['label']}"
                f"_container_{index}.html"
            ),
            str(container)
        )

    result["products"] = products

    return result


# ============================================================
# FIND ALL QUANTITY BLOCKS
# ============================================================

def analyze_quantity(source, label):

    print()
    print("=" * 80)
    print(f"QUANTITY ANALYSIS: {label}")
    print("=" * 80)

    matches = list(
        re.finditer(
            r"quantity",
            source,
            flags=re.I
        )
    )

    print(
        f"Total 'quantity' occurrences: "
        f"{len(matches)}"
    )

    contexts = []

    for index, match in enumerate(
        matches,
        start=1
    ):

        start = max(
            0,
            match.start() - 700
        )

        end = min(
            len(source),
            match.end() + 1200
        )

        context = source[
            start:end
        ]

        contexts.append({
            "number": index,
            "position": match.start(),
            "context": context
        })

        print()
        print(
            f"--- quantity #{index} "
            f"at {match.start()} ---"
        )

        print(
            context[:1900]
        )

    save_file(
        f"{label}_quantity_contexts.txt",
        "\n\n".join(
            item["context"]
            for item in contexts
        )
    )


# ============================================================
# FIND PRICE BLOCKS
# ============================================================

def analyze_price(source, label):

    print()
    print("=" * 80)
    print(f"PRICE ANALYSIS: {label}")
    print("=" * 80)

    matches = list(
        re.finditer(
            r"price",
            source,
            flags=re.I
        )
    )

    print(
        f"Total 'price' occurrences: "
        f"{len(matches)}"
    )

    contexts = []

    for index, match in enumerate(
        matches,
        start=1
    ):

        start = max(
            0,
            match.start() - 500
        )

        end = min(
            len(source),
            match.end() + 900
        )

        context = source[
            start:end
        ]

        contexts.append({
            "number": index,
            "position": match.start(),
            "context": context
        })

        print()
        print(
            f"--- price #{index} "
            f"at {match.start()} ---"
        )

        print(
            context[:1400]
        )

    save_file(
        f"{label}_price_contexts.txt",
        "\n\n".join(
            item["context"]
            for item in contexts
        )
    )


# ============================================================
# FIND STORES
# ============================================================

def analyze_stores(source, label):

    print()
    print("=" * 80)
    print(f"STORES ANALYSIS: {label}")
    print("=" * 80)

    matches = list(
        re.finditer(
            r"stores",
            source,
            flags=re.I
        )
    )

    print(
        f"Total 'stores' occurrences: "
        f"{len(matches)}"
    )

    contexts = []

    for index, match in enumerate(
        matches,
        start=1
    ):

        start = max(
            0,
            match.start() - 800
        )

        end = min(
            len(source),
            match.end() + 1800
        )

        context = source[
            start:end
        ]

        contexts.append({
            "number": index,
            "position": match.start(),
            "context": context
        })

        print()
        print(
            f"--- stores #{index} "
            f"at {match.start()} ---"
        )

        print(
            context[:2500]
        )

    save_file(
        f"{label}_stores_contexts.txt",
        "\n\n".join(
            item["context"]
            for item in contexts
        )
    )


# ============================================================
# SKU CONTEXT
# ============================================================

def analyze_sku_context(
    source,
    term,
    label
):

    print()
    print("=" * 80)
    print(
        f"TERM CONTEXT: {label}"
    )
    print("=" * 80)

    positions = []

    start = 0

    while True:

        position = source.find(
            term,
            start
        )

        if position == -1:
            break

        positions.append(
            position
        )

        start = position + len(term)

    print(
        f"Occurrences of "
        f"'{term}': "
        f"{len(positions)}"
    )

    contexts = []

    for index, position in enumerate(
        positions,
        start=1
    ):

        left = max(
            0,
            position - 1000
        )

        right = min(
            len(source),
            position + len(term) + 1500
        )

        context = source[
            left:right
        ]

        contexts.append(
            context
        )

        print()
        print(
            f"--- occurrence #{index} "
            f"at {position} ---"
        )

        print(
            context
        )

    save_file(
        f"{label}_term_contexts.txt",
        "\n\n".join(
            contexts
        )
    )


# ============================================================
# COMPARE RESULTS
# ============================================================

def compare_results(results):

    print()
    print("=" * 80)
    print("RESPONSE COMPARISON")
    print("=" * 80)

    for i in range(
        len(results)
    ):

        for j in range(
            i + 1,
            len(results)
        ):

            a = results[i]
            b = results[j]

            print()
            print(
                f"{a['label']} "
                f"VS "
                f"{b['label']}"
            )

            print(
                f"Raw SHA256 equal: "
                f"{a['raw_hash'] == b['raw_hash']}"
            )

            print(
                f"Normalized SHA256 equal: "
                f"{a['normalized_hash'] == b['normalized_hash']}"
            )

            print(
                f"Size difference: "
                f"{a['size'] - b['size']}"
            )


# ============================================================
# PRODUCT ID SUMMARY
# ============================================================

def product_id_summary(results):

    print()
    print("=" * 80)
    print("PRODUCT ID SUMMARY")
    print("=" * 80)

    summary = {}

    for result in results:

        ids = []

        for product in result.get(
            "products",
            []
        ):

            product_id = product.get(
                "data-product-id"
            )

            if product_id:
                ids.append(
                    product_id
                )

        summary[
            result["label"]
        ] = ids

        print(
            f"{result['label']}: "
            f"{ids}"
        )

    save_file(
        "comparison_product_ids.json",
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2
        )
    )


# ============================================================
# MAIN
# ============================================================

def main():

    os.makedirs(
        DEBUG_DIR,
        exist_ok=True
    )

    print(
        "=" * 80
    )

    print(
        "FILSTAR /api/search DEEP DIAGNOSTIC"
    )

    print(
        "=" * 80
    )

    print()
    print(
        "Използва се САМО /api/search."
    )

    print()
    print(
        "Не се използват:"
    )

    print(
        "  - /search"
    )

    print(
        "  - /get-serialize-product/"
    )

    print(
        "  - /search-json-typesense"
    )

    print(
        "  - product page"
    )

    print(
        "  - Selenium"
    )

    print(
        "  - Playwright"
    )

    print(
        "  - Cloudflare bypass"
    )

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    results = []

    # ========================================================
    # RUN TESTS
    # ========================================================

    for term, label in TESTS:

        result = api_search(
            session,
            term,
            label
        )

        if not result:
            continue

        analyze_products(
            result
        )

        analyze_quantity(
            result["source"],
            label
        )

        analyze_price(
            result["source"],
            label
        )

        analyze_stores(
            result["source"],
            label
        )

        analyze_sku_context(
            result["source"],
            term,
            label
        )

        results.append(
            result
        )

    # ========================================================
    # COMPARE
    # ========================================================

    compare_results(
        results
    )

    product_id_summary(
        results
    )

    # ========================================================
    # FINAL JSON
    # ========================================================

    final_summary = []

    for result in results:

        final_summary.append({
            "term": result["term"],
            "label": result["label"],
            "status": result["status"],
            "size": result["size"],
            "raw_hash": result["raw_hash"],
            "normalized_hash": result[
                "normalized_hash"
            ],
            "product_ids": [
                p.get(
                    "data-product-id"
                )
                for p in result.get(
                    "products",
                    []
                )
                if p.get(
                    "data-product-id"
                )
            ],
        })

    save_file(
        "FINAL_COMPARISON.json",
        json.dumps(
            final_summary,
            ensure_ascii=False,
            indent=2
        )
    )

    print()
    print(
        "=" * 80
    )

    print(
        "DIAGNOSTIC FINISHED"
    )

    print(
        "=" * 80
    )

    print()
    print(
        f"Всички debug файлове са в: "
        f"{DEBUG_DIR}/"
    )

    print()
    print(
        "Най-важните файлове са:"
    )

    print(
        "  FINAL_COMPARISON.json"
    )

    print(
        "  comparison_product_ids.json"
    )

    print(
        "  sku_946537_quantity_contexts.txt"
    )

    print(
        "  sku_946534_quantity_contexts.txt"
    )

    print(
        "  sku_946535_quantity_contexts.txt"
    )

    print(
        "  sku_946537_price_contexts.txt"
    )

    print(
        "  sku_946534_price_contexts.txt"
    )

    print(
        "  sku_946535_price_contexts.txt"
    )


if __name__ == "__main__":
    main()
