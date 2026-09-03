import requests
from bs4 import BeautifulSoup
import re
import json
from pathlib import Path


BASE_URL = "https://filstar.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "bg-BG,bg;q=0.9,en-US;q=0.8,en;q=0.7",
}


DEBUG_DIR = Path("debug_html")
DEBUG_DIR.mkdir(exist_ok=True)


def print_header(title):
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)


def show_context(text, term, radius=500):
    """
    Показва контекста около даден текст.
    """
    positions = [
        m.start()
        for m in re.finditer(
            re.escape(term),
            text,
            flags=re.IGNORECASE
        )
    ]

    print(f"TERM: {term!r}")
    print(f"COUNT: {len(positions)}")

    for i, pos in enumerate(positions[:20], 1):

        start = max(0, pos - radius)
        end = min(len(text), pos + radius)

        print()
        print(f"--- OCCURRENCE #{i} ---")
        print(text[start:end])


def extract_json_scripts(soup):

    print_header("JSON SCRIPT BLOCKS")

    scripts = soup.find_all("script")

    print(f"TOTAL SCRIPT TAGS: {len(scripts)}")

    found = 0

    for i, script in enumerate(scripts, 1):

        script_type = script.get("type", "")
        content = script.string or script.get_text()

        if not content:
            continue

        content_lower = content.lower()

        interesting = (
            "application/json" in script_type.lower()
            or "ld+json" in script_type.lower()
            or "946537" in content
            or "946534" in content
            or '"variants"' in content_lower
            or '"quantity"' in content_lower
            or '"barcode"' in content_lower
            or "defaultvariant" in content_lower
        )

        if not interesting:
            continue

        found += 1

        print()
        print(f"SCRIPT #{i}")
        print("-" * 80)
        print("TYPE:", script_type)
        print("SIZE:", len(content))

        print(content[:20000])

    print()
    print("INTERESTING SCRIPT BLOCKS:", found)


def inspect_data_attributes(soup):

    print_header("DATA ATTRIBUTES")

    found = 0

    interesting_words = (
        "product",
        "variant",
        "sku",
        "barcode",
        "quantity",
        "stock",
        "price",
        "store",
        "serialize",
        "endpoint",
        "url",
        "json",
    )

    for tag in soup.find_all(True):

        matches = {}

        for key, value in tag.attrs.items():

            key_lower = key.lower()

            value_string = str(value).lower()

            if (
                any(word in key_lower for word in interesting_words)
                or any(word in value_string for word in interesting_words)
            ):
                matches[key] = value

        if not matches:
            continue

        found += 1

        print()
        print(f"<{tag.name}>")

        for key, value in matches.items():

            print(
                f"  {key} = {value}"
            )

    print()
    print("INTERESTING ELEMENTS:", found)


def inspect_hidden_inputs(soup):

    print_header("HIDDEN INPUTS")

    inputs = soup.find_all("input")

    print("TOTAL INPUTS:", len(inputs))

    for inp in inputs:

        input_type = inp.get("type", "").lower()

        if input_type == "hidden":

            print(
                inp.attrs
            )


def inspect_vue_related(soup):

    print_header("VUE / PRODUCT RELATED HTML")

    html = str(soup)

    terms = [
        "vue",
        "__vue__",
        "variants",
        "defaultVariant",
        "availableVariants",
        "selectedVariant",
        "variant_id",
        "variantId",
        "product_id",
        "productId",
        "getProductSerializeUrl",
        "get-serialize-product",
        "946537",
        "946534",
        "8617",
        "8618",
        "quantity",
        "barcode",
        "stores",
        "maxQuantityByStores",
    ]

    for term in terms:

        positions = [
            m.start()
            for m in re.finditer(
                re.escape(term),
                html,
                flags=re.IGNORECASE
            )
        ]

        print(
            f"{term!r}: {len(positions)}"
        )


def extract_urls(soup):

    print_header("INTERESTING URLS")

    urls = set()

    for tag in soup.find_all(True):

        for attr in ("href", "src", "action"):

            value = tag.get(attr)

            if not value:
                continue

            value = str(value)

            if any(
                word in value.lower()
                for word in (
                    "product",
                    "variant",
                    "serialize",
                    "api",
                    "json",
                    "search",
                    "cart",
                )
            ):

                urls.add(value)

    for url in sorted(urls):

        print(url)

    print()
    print("TOTAL:", len(urls))


def inspect_product_containers(soup):

    print_header("PRODUCT CONTAINERS")

    products = soup.select(
        ".product-item-wapper"
    )

    print(
        "TOTAL:",
        len(products)
    )

    for i, product in enumerate(products, 1):

        print()
        print(f"PRODUCT #{i}")
        print("-" * 80)

        print(
            "TEXT:",
            product.get_text(
                " ",
                strip=True
            )
        )

        print()

        for key, value in product.attrs.items():

            print(
                f"ROOT ATTRIBUTE: {key} = {value}"
            )

        for tag in product.find_all(True):

            for key, value in tag.attrs.items():

                key_lower = key.lower()

                if any(
                    word in key_lower
                    for word in (
                        "product",
                        "variant",
                        "sku",
                        "price",
                        "quantity",
                        "stock",
                        "store",
                        "data",
                    )
                ):

                    print(
                        f"<{tag.name}> {key} = {value}"
                    )


def search_possible_json(text):

    print_header("POSSIBLE JSON OBJECTS")

    candidates = []

    # ---------------------------------------------------------
    # JSON-LD
    # ---------------------------------------------------------

    for match in re.finditer(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        text,
        flags=re.IGNORECASE | re.DOTALL
    ):

        candidates.append(
            match.group(1)
        )

    # ---------------------------------------------------------
    # COMMON INITIAL STATE VARIABLES
    # ---------------------------------------------------------

    patterns = [
        r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;',
        r'window\.initialState\s*=\s*(\{.*?\})\s*;',
        r'window\.__INITIAL_DATA__\s*=\s*(\{.*?\})\s*;',
        r'window\.initialData\s*=\s*(\{.*?\})\s*;',
    ]

    for pattern in patterns:

        for match in re.finditer(
            pattern,
            text,
            flags=re.IGNORECASE | re.DOTALL
        ):

            candidates.append(
                match.group(1)
            )

    print(
        "CANDIDATES:",
        len(candidates)
    )

    for i, candidate in enumerate(
        candidates,
        1
    ):

        print()
        print(
            f"JSON CANDIDATE #{i}"
        )

        print(
            candidate[:20000]
        )

        try:

            data = json.loads(candidate)

            print()
            print("VALID JSON: YES")
            print(
                "TOP LEVEL TYPE:",
                type(data).__name__
            )

            if isinstance(data, dict):

                print(
                    "KEYS:",
                    list(data.keys())[:100]
                )

        except Exception as e:

            print(
                "VALID JSON: NO"
            )

            print(
                "ERROR:",
                e
            )


def find_skus(text):

    print_header("SKU / VARIANT SEARCH")

    known_skus = [
        "946537",
        "946534",
        "946535",
        "946536",
        "951786",
        "951787",
    ]

    variant_ids = [
        "8617",
        "8618",
        "8619",
        "8620",
        "8621",
        "8622",
    ]

    terms = known_skus + variant_ids

    for term in terms:

        show_context(
            text,
            term,
            radius=350
        )


def find_product_state_patterns(text):

    print_header("PRODUCT STATE PATTERNS")

    patterns = [
        r'product\s*[:=]',
        r'variants\s*[:=]',
        r'defaultVariant\s*[:=]',
        r'availableVariants\s*[:=]',
        r'selectedVariant\s*[:=]',
        r'quantity\s*[:=]',
        r'barcode\s*[:=]',
        r'stores\s*[:=]',
        r'maxQuantityByStores\s*[:=]',
        r'variant_id',
        r'variantId',
        r'product_id',
        r'productId',
    ]

    for pattern in patterns:

        matches = list(
            re.finditer(
                pattern,
                text,
                flags=re.IGNORECASE
            )
        )

        print(
            f"{pattern!r}: {len(matches)}"
        )

        for match in matches[:5]:

            start = max(
                0,
                match.start() - 300
            )

            end = min(
                len(text),
                match.end() + 700
            )

            print()
            print(
                text[start:end]
            )


def main():

    sku = "946537"

    url = (
        f"{BASE_URL}/api/search"
        f"?term={sku}"
    )

    print_header(
        "FILSTAR /api/search DEEP DIAGNOSTIC"
    )

    print(
        "URL:",
        url
    )

    try:

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

    except Exception as e:

        print()
        print(
            "REQUEST ERROR:",
            repr(e)
        )

        return

    print()
    print(
        "STATUS:",
        r.status_code
    )

    print(
        "CONTENT TYPE:",
        r.headers.get("Content-Type")
    )

    print(
        "SIZE:",
        f"{len(r.text):,}"
    )

    # ---------------------------------------------------------
    # SAVE RAW RESPONSE
    # ---------------------------------------------------------

    raw_file = (
        DEBUG_DIR /
        f"api_search_{sku}.html"
    )

    raw_file.write_text(
        r.text,
        encoding="utf-8"
    )

    print()
    print(
        "RAW HTML SAVED:",
        raw_file
    )

    # ---------------------------------------------------------
    # SOUP
    # ---------------------------------------------------------

    soup = BeautifulSoup(
        r.text,
        "html.parser"
    )

    # ---------------------------------------------------------
    # BASIC
    # ---------------------------------------------------------

    print_header(
        "BASIC HTML INFORMATION"
    )

    print(
        "TITLE:",
        soup.title.get_text(
            strip=True
        )
        if soup.title
        else None
    )

    print(
        "SCRIPT TAGS:",
        len(soup.find_all("script"))
    )

    print(
        "LINK TAGS:",
        len(soup.find_all("link"))
    )

    print(
        "DIV TAGS:",
        len(soup.find_all("div"))
    )

    # ---------------------------------------------------------
    # PRODUCT
    # ---------------------------------------------------------

    inspect_product_containers(
        soup
    )

    # ---------------------------------------------------------
    # JSON
    # ---------------------------------------------------------

    extract_json_scripts(
        soup
    )

    search_possible_json(
        r.text
    )

    # ---------------------------------------------------------
    # DATA ATTRIBUTES
    # ---------------------------------------------------------

    inspect_data_attributes(
        soup
    )

    # ---------------------------------------------------------
    # HIDDEN INPUTS
    # ---------------------------------------------------------

    inspect_hidden_inputs(
        soup
    )

    # ---------------------------------------------------------
    # URLS
    # ---------------------------------------------------------

    extract_urls(
        soup
    )

    # ---------------------------------------------------------
    # VUE
    # ---------------------------------------------------------

    inspect_vue_related(
        soup
    )

    # ---------------------------------------------------------
    # SKU
    # ---------------------------------------------------------

    find_skus(
        r.text
    )

    # ---------------------------------------------------------
    # STATE PATTERNS
    # ---------------------------------------------------------

    find_product_state_patterns(
        r.text
    )

    # ---------------------------------------------------------
    # GLOBAL KEYWORD COUNTS
    # ---------------------------------------------------------

    print_header(
        "GLOBAL KEYWORD COUNTS"
    )

    keywords = [
        "variant",
        "variants",
        "defaultVariant",
        "availableVariants",
        "selectedVariant",
        "quantity",
        "stock",
        "price",
        "discountedPrice",
        "originalPrice",
        "barcode",
        "stores",
        "store",
        "maxQuantityByStores",
        "productId",
        "product_id",
        "variantId",
        "variant_id",
        "sku",
        "946537",
        "946534",
        "946535",
        "946536",
        "951786",
        "951787",
        "8617",
        "8618",
        "8619",
        "8620",
        "8621",
        "8622",
    ]

    lower_text = r.text.lower()

    for keyword in keywords:

        count = lower_text.count(
            keyword.lower()
        )

        print(
            f"{keyword:25} = {count}"
        )

    # ---------------------------------------------------------
    # END
    # ---------------------------------------------------------

    print_header(
        "END OF DIAGNOSTIC"
    )

    print(
        "Raw response:",
        raw_file
    )

    print(
        "If variants are hidden in the /api/search response,"
        " the relevant context should now be visible above."
    )


if __name__ == "__main__":
    main()
