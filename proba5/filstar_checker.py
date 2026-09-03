import os
import re
import json
import html
import csv
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://filstar.com"
CSV_FILE = "sku_list_filstar.csv"
DEBUG_DIR = "debug_html"

TEST_SKUS = [
    "946537",
    "946534",
    "946535",
]

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
# SAVE
# ============================================================

def save_text(filename, content):
    os.makedirs(DEBUG_DIR, exist_ok=True)

    path = os.path.join(DEBUG_DIR, filename)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return path


# ============================================================
# EXACT OCCURRENCES
# ============================================================

def find_occurrences(text, sku):
    positions = []

    start = 0

    while True:
        pos = text.find(sku, start)

        if pos == -1:
            break

        positions.append(pos)
        start = pos + len(sku)

    return positions


# ============================================================
# TAG AROUND SKU
# ============================================================

def get_tag(text, position):
    left = text.rfind("<", 0, position)
    right = text.find(">", position)

    if left == -1 or right == -1:
        return ""

    tag = text[left:right + 1]

    if len(tag) > 5000:
        tag = tag[:5000] + "\n...[TRUNCATED]..."

    return tag


# ============================================================
# ATTRIBUTES
# ============================================================

def extract_attributes(tag):
    result = {}

    match = re.match(
        r"<\s*([a-zA-Z0-9:_-]+)",
        tag
    )

    if match:
        result["_tag"] = match.group(1)

    attributes = re.findall(
        r'([a-zA-Z_:][a-zA-Z0-9_:.-]*)\s*=\s*["\']([^"\']*)["\']',
        tag
    )

    for key, value in attributes:
        result[key] = html.unescape(value)

    return result


# ============================================================
# PRODUCT CONTAINERS
# ============================================================

def find_product_containers(source):
    """
    Намира product-item-wapper блоков.
    """

    pattern = re.compile(
        r'<div\b[^>]*class\s*=\s*["\'][^"\']*product-item-wapper[^"\']*["\'][^>]*>',
        re.I
    )

    containers = []

    for match in pattern.finditer(source):

        start = match.start()
        opening_tag = match.group(0)

        depth = 0
        pos = start

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

                    containers.append({
                        "start": start,
                        "end": end,
                        "html": source[start:end],
                        "opening_tag": opening_tag
                    })

                    break

    return containers


# ============================================================
# PRODUCT CONTAINER ANALYSIS
# ============================================================

def analyze_product_containers(source, sku):

    print()
    print("=" * 60)
    print("PRODUCT CONTAINERS")
    print("=" * 60)

    containers = find_product_containers(source)

    print(
        f"Product containers: {len(containers)}"
    )

    output = []

    for index, container in enumerate(
        containers,
        start=1
    ):

        container_html = container["html"]

        print()
        print(
            f"Container #{index}"
        )

        print(
            f"Size: {len(container_html):,} bytes"
        )

        attrs = extract_attributes(
            container["opening_tag"]
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
            f"Category: "
            f"{attrs.get('data-product-category', 'N/A')}"
        )

        # HREFs
        hrefs = re.findall(
            r'href\s*=\s*["\']([^"\']+)["\']',
            container_html,
            re.I
        )

        print(
            f"HREFs: {hrefs[:10]}"
        )

        # Всички data-* атрибути
        data_attrs = {}

        for key, value in re.findall(
            r'(data-[a-zA-Z0-9:_-]+)\s*=\s*["\']([^"\']*)["\']',
            container_html
        ):
            data_attrs[key] = html.unescape(value)

        print("Data attributes:")

        for key, value in data_attrs.items():
            print(
                f"   {key} = {value}"
            )

        # SKU occurrences
        occurrences = find_occurrences(
            container_html,
            sku
        )

        print(
            f"SKU {sku} occurrences: "
            f"{len(occurrences)}"
        )

        # price
        price_matches = re.findall(
            r'.{0,300}(?:price|цена).{0,500}',
            container_html,
            re.I | re.S
        )

        # quantity
        quantity_matches = re.findall(
            r'.{0,300}(?:quantity|количество|наличност).{0,500}',
            container_html,
            re.I | re.S
        )

        # variant
        variant_matches = re.findall(
            r'.{0,300}variant.{0,500}',
            container_html,
            re.I | re.S
        )

        output.append({
            "container_number": index,
            "size": len(container_html),
            "attributes": attrs,
            "data_attributes": data_attrs,
            "hrefs": hrefs,
            "sku_occurrences": occurrences,
            "price_matches": price_matches,
            "quantity_matches": quantity_matches,
            "variant_matches": variant_matches,
            "html": container_html
        })

        # ----------------------------------------------------
        # SAVE CONTAINER
        # ----------------------------------------------------

        save_text(
            f"search_{sku}_container_{index}.html",
            container_html
        )

    return output


# ============================================================
# SKU CONTEXT
# ============================================================

def analyze_sku_occurrences(source, sku):

    print()
    print("=" * 60)
    print(f"ALL SKU OCCURRENCES: {sku}")
    print("=" * 60)

    positions = find_occurrences(
        source,
        sku
    )

    print(
        f"Exact occurrences: {len(positions)}"
    )

    output = []

    for index, position in enumerate(
        positions,
        start=1
    ):

        tag = get_tag(
            source,
            position
        )

        attrs = extract_attributes(tag)

        start = max(
            0,
            position - 2000
        )

        end = min(
            len(source),
            position + len(sku) + 2000
        )

        context = source[start:end]

        print()
        print(
            f"#{index}"
        )

        print(
            f"Position: {position:,}"
        )

        print(
            f"Tag: {tag[:1000]}"
        )

        print(
            f"Attributes: "
            f"{json.dumps(attrs, ensure_ascii=False)}"
        )

        output.append({
            "occurrence": index,
            "position": position,
            "tag": tag,
            "attributes": attrs,
            "context": context
        })

    # --------------------------------------------------------
    # SAVE SUMMARY
    # --------------------------------------------------------

    summary = []

    for item in output:

        summary.append(
            "=" * 100
        )

        summary.append(
            f"OCCURRENCE #{item['occurrence']}"
        )

        summary.append(
            f"Position: {item['position']}"
        )

        summary.append(
            f"Tag:\n{item['tag']}"
        )

        summary.append(
            "Attributes:"
        )

        summary.append(
            json.dumps(
                item["attributes"],
                ensure_ascii=False,
                indent=2
            )
        )

        summary.append(
            "Context:"
        )

        summary.append(
            item["context"]
        )

        summary.append("")

    save_text(
        f"search_{sku}_occurrences.txt",
        "\n".join(summary)
    )

    return output


# ============================================================
# SEARCH PAGE
# ============================================================

def test_search_page(session, sku):

    print()
    print("=" * 70)
    print(f"SEARCH PAGE: {sku}")
    print("=" * 70)

    url = f"{BASE_URL}/search"

    try:

        response = session.get(
            url,
            params={"term": sku},
            headers=HEADERS,
            timeout=30
        )

    except Exception as e:

        print(
            f"❌ ERROR: {e}"
        )

        return

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
        f"Size: {len(response.content):,} bytes"
    )

    source = response.text

    # --------------------------------------------------------
    # SAVE RAW
    # --------------------------------------------------------

    raw_path = save_text(
        f"search_page_{sku}.html",
        source
    )

    print(
        f"💾 Raw HTML: {raw_path}"
    )

    # --------------------------------------------------------
    # SEARCH SKU
    # --------------------------------------------------------

    occurrences = analyze_sku_occurrences(
        source,
        sku
    )

    # --------------------------------------------------------
    # PRODUCT CONTAINERS
    # --------------------------------------------------------

    containers = analyze_product_containers(
        source,
        sku
    )

    # --------------------------------------------------------
    # GLOBAL KEYWORD SEARCH
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("GLOBAL KEYWORD SEARCH")
    print("=" * 60)

    keywords = [
        "product-item-wapper",
        "data-product-id",
        "data-product-variant",
        "quantity",
        "price",
        "variant",
        "search-json-typesense",
        "autocomplete",
        "946537",
        "946534",
        "946535",
    ]

    keyword_summary = {}

    lower_source = source.lower()

    for keyword in keywords:

        count = lower_source.count(
            keyword.lower()
        )

        keyword_summary[keyword] = count

        print(
            f"{keyword}: {count}"
        )

    save_text(
        f"search_page_{sku}_keywords.json",
        json.dumps(
            keyword_summary,
            ensure_ascii=False,
            indent=2
        )
    )

    # --------------------------------------------------------
    # LOOK FOR ALL PRODUCT IDs
    # --------------------------------------------------------

    product_ids = re.findall(
        r'data-product-id\s*=\s*["\']([^"\']+)["\']',
        source,
        re.I
    )

    print()
    print(
        "Product IDs:"
    )

    unique_product_ids = []

    for product_id in product_ids:

        if product_id not in unique_product_ids:
            unique_product_ids.append(product_id)

    for product_id in unique_product_ids:
        print(
            f"   {product_id}"
        )

    save_text(
        f"search_page_{sku}_product_ids.txt",
        "\n".join(unique_product_ids)
    )

    # --------------------------------------------------------
    # LOOK FOR ALL HREFs TO PRODUCT
    # --------------------------------------------------------

    product_hrefs = []

    for href in re.findall(
        r'href\s*=\s*["\']([^"\']+)["\']',
        source,
        re.I
    ):

        if href not in product_hrefs:
            product_hrefs.append(href)

    relevant_hrefs = [
        href
        for href in product_hrefs
        if href.startswith("/")
    ]

    save_text(
        f"search_page_{sku}_hrefs.txt",
        "\n".join(relevant_hrefs)
    )

    print()
    print(
        f"Internal HREFs: {len(relevant_hrefs)}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("FILSTAR /search?term=SKU DIAGNOSTIC")
    print("=" * 70)

    os.makedirs(
        DEBUG_DIR,
        exist_ok=True
    )

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    for index, sku in enumerate(
        TEST_SKUS,
        start=1
    ):

        print()
        print("=" * 70)

        print(
            f"SKU {index}/{len(TEST_SKUS)}: {sku}"
        )

        print("=" * 70)

        test_search_page(
            session,
            sku
        )

    print()
    print("=" * 70)
    print("DIAGNOSTIC FINISHED")
    print("=" * 70)

    print(
        f"Debug folder: {DEBUG_DIR}"
    )

    print()
    print(
        "Проверени са:"
    )

    print(
        "   /search?term=946537"
    )

    print(
        "   /search?term=946534"
    )

    print(
        "   /search?term=946535"
    )

    print()
    print(
        "НЕ са използвани:"
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


if __name__ == "__main__":
    main()
