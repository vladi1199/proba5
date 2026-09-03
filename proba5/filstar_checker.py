import csv
import json
import os
import re
import shutil
import time

from urllib.parse import quote, urljoin

import requests


BASE_URL = "https://filstar.com"
WAIT = 2

CSV_FILE = "sku_list_filstar.csv"
RESULTS_FILE = "results_filstar.csv"
NOT_FOUND_FILE = "not_found_filstar.csv"
DEBUG_DIR = "debug_html"


# ============================================================
# CSV
# ============================================================

def read_skus():
    skus = []

    with open(
        CSV_FILE,
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            sku = str(
                row.get("SKU", "")
            ).strip()

            if not sku:
                continue

            # Поддръжка на блокови коментари:
            #
            # ##
            # SKU...
            # SKU...
            # ##
            #
            # Всичко между ## и ## се игнорира.

            if not hasattr(read_skus, "in_comment"):
                read_skus.in_comment = False

            if sku == "##":
                read_skus.in_comment = not read_skus.in_comment
                continue

            if read_skus.in_comment:
                continue

            skus.append(sku)

    return skus


# ============================================================
# DEBUG
# ============================================================

def init_debug_folder():
    if os.path.exists(DEBUG_DIR):
        shutil.rmtree(DEBUG_DIR)

    os.makedirs(
        DEBUG_DIR,
        exist_ok=True,
    )


def save_debug(filename, content):
    path = os.path.join(
        DEBUG_DIR,
        filename,
    )

    folder = os.path.dirname(path)

    if folder:
        os.makedirs(
            folder,
            exist_ok=True,
        )

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as f:

        f.write(
            content
            if isinstance(content, str)
            else str(content)
        )


# ============================================================
# CSV RESULTS
# ============================================================

def init_csv():
    with open(
        RESULTS_FILE,
        "w",
        encoding="utf-8",
        newline="",
    ) as f:

        writer = csv.writer(f)

        writer.writerow(
            [
                "SKU",
                "Наличност",
                "Бройки",
                "Цена",
            ]
        )


def save_result(
    sku,
    availability,
    quantity,
    price,
):

    with open(
        RESULTS_FILE,
        "a",
        encoding="utf-8",
        newline="",
    ) as f:

        writer = csv.writer(f)

        writer.writerow(
            [
                sku,
                availability,
                quantity,
                price,
            ]
        )


def save_not_found(sku):

    with open(
        NOT_FOUND_FILE,
        "a",
        encoding="utf-8",
        newline="",
    ) as f:

        writer = csv.writer(f)

        writer.writerow(
            [sku]
        )


# ============================================================
# SEARCH
# ============================================================

def search_filstar(
    session,
    sku,
):

    url = (
        BASE_URL
        + "/api/search?term="
        + quote(str(sku))
    )

    try:

        response = session.get(
            url,
            timeout=30,
        )

        print(
            f"   🔎 /api/search?term={sku} → "
            f"HTTP {response.status_code}"
        )

        print(
            f"   Content-Type: "
            f"{response.headers.get('Content-Type')}"
        )

        print(
            f"   Размер: "
            f"{len(response.text):,} bytes"
        )

        save_debug(
            f"search_{sku}.html",
            response.text,
        )

        return response.text

    except Exception as e:

        print(
            "   ❌ Search error:",
            repr(e),
        )

        return None


# ============================================================
# PRODUCT ID
# ============================================================

def extract_product_id(html):

    if not html:
        return None

    # Най-прекият вариант:
    # data-product-id="2557"

    match = re.search(
        r'data-product-id=["\'](\d+)["\']',
        html,
        re.I,
    )

    if match:

        product_id = match.group(1)

        print(
            "   🆔 Product ID:",
            product_id,
        )

        return product_id

    # Резервен вариант

    patterns = [
        r'"productId"\s*:\s*"?(\d+)',
        r'"product_id"\s*:\s*"?(\d+)',
        r'data-product-id\s*=\s*[\'"](\d+)',
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.I,
        )

        if match:

            product_id = match.group(1)

            print(
                "   🆔 Product ID:",
                product_id,
            )

            return product_id

    print(
        "   ❌ Product ID not found"
    )

    return None


# ============================================================
# PRODUCT URL
# ============================================================

def extract_product_url(
    html,
    sku=None,
):

    if not html:
        return None

    # --------------------------------------------------------
    # Първо търсим product-item-wapper контейнер,
    # който съдържа конкретния SKU.
    # --------------------------------------------------------

    if sku:

        sku = str(sku)

        starts = list(
            re.finditer(
                r'<div[^>]*class=["\'][^"\']*product-item-wapper[^"\']*["\'][^>]*>',
                html,
                re.I,
            )
        )

        for index, match in enumerate(
            starts
        ):

            start_pos = match.start()

            if index + 1 < len(starts):

                end_pos = starts[
                    index + 1
                ].start()

            else:

                end_pos = len(html)

            container = html[
                start_pos:end_pos
            ]

            if sku not in container:
                continue

            hrefs = re.findall(
                r'href=["\']([^"\']+)["\']',
                container,
                re.I,
            )

            for href in hrefs:

                if (
                    href.startswith("/")
                    and not href.startswith(
                        (
                            "/search",
                            "/api/",
                            "/cart/",
                            "/login",
                            "/register",
                            "/manifest",
                        )
                    )
                ):

                    full_url = urljoin(
                        BASE_URL,
                        href,
                    )

                    print(
                        "   🔗 Product URL:",
                        full_url,
                    )

                    return full_url

    # --------------------------------------------------------
    # Резервен вариант:
    # Търсим URL около SKU.
    # --------------------------------------------------------

    if sku:

        pattern = (
            r'href=["\']([^"\']+)["\'][^>]*>'
            r'.{0,5000}?'
            + re.escape(str(sku))
        )

        match = re.search(
            pattern,
            html,
            re.I | re.S,
        )

        if match:

            href = match.group(1)

            if href.startswith("/"):
                return urljoin(
                    BASE_URL,
                    href,
                )

    print(
        "   ❌ Product URL not found"
    )

    return None


# ============================================================
# ALL URLS
# ============================================================

def extract_all_urls(html):

    if not html:
        return []

    urls = re.findall(
        r'href=["\']([^"\']+)["\']',
        html,
        re.I,
    )

    result = []

    for url in urls:

        full = urljoin(
            BASE_URL,
            url,
        )

        if full not in result:
            result.append(full)

    return result


# ============================================================
# CONTEXT
# ============================================================

def extract_context(
    text,
    keyword,
    radius=1000,
):

    if not text:
        return ""

    positions = [
        m.start()
        for m in re.finditer(
            re.escape(str(keyword)),
            text,
            re.I,
        )
    ]

    if not positions:
        return ""

    output = []

    for pos in positions[:20]:

        start = max(
            0,
            pos - radius,
        )

        end = min(
            len(text),
            pos + radius,
        )

        output.append(
            "\n"
            + "=" * 80
            + "\n"
            + f"KEYWORD: {keyword}\n"
            + f"POSITION: {pos}\n"
            + "=" * 80
            + "\n"
            + text[start:end]
        )

    return "\n".join(
        output
    )


# ============================================================
# PRODUCT CONTAINER INSPECTION
# ============================================================

def inspect_product_container(
    html,
    sku,
):

    if not html:
        return None

    sku = str(sku)

    print()
    print(
        "=" * 60
    )
    print(
        "INSPECT PRODUCT CONTAINER"
    )
    print(
        "=" * 60
    )

    starts = list(
        re.finditer(
            r'<div[^>]*class=["\'][^"\']*product-item-wapper[^"\']*["\'][^>]*>',
            html,
            re.I,
        )
    )

    print(
        "Product containers:",
        len(starts),
    )

    for index, match in enumerate(
        starts,
        1,
    ):

        start_pos = match.start()

        if index < len(starts):

            end_pos = starts[
                index
            ].start()

        else:

            end_pos = len(html)

        container = html[
            start_pos:end_pos
        ]

        if sku not in container:
            continue

        print(
            "Намерен контейнер за SKU:",
            sku,
        )

        print(
            "Container size:",
            len(container),
            "bytes",
        )

        # ----------------------------------------------------
        # Целият container
        # ----------------------------------------------------

        save_debug(
            f"product_container_{sku}.html",
            container,
        )

        # ----------------------------------------------------
        # DATA ATTRIBUTES
        # ----------------------------------------------------

        data_attributes = re.findall(
            r'\bdata-[a-zA-Z0-9_-]+=["\']([^"\']*)["\']',
            container,
            re.I,
        )

        if data_attributes:

            save_debug(
                f"product_container_{sku}_data.txt",
                "\n".join(
                    data_attributes
                ),
            )

            print(
                "Data attributes:",
                len(data_attributes),
            )

        # ----------------------------------------------------
        # HREFS
        # ----------------------------------------------------

        hrefs = re.findall(
            r'href=["\']([^"\']+)["\']',
            container,
            re.I,
        )

        print(
            "HREF:",
            hrefs,
        )

        # ----------------------------------------------------
        # KEYWORDS
        # ----------------------------------------------------

        keywords = [
            sku,
            "variants",
            "variant",
            "quantity",
            "price",
            "discountedPrice",
            "discountedRetailPrice",
            "traderPrice",
            "stores",
            "maxQuantity",
            "maxQuantityByStores",
            "8617",
            "8618",
            "946534",
            "946537",
            "3809909465340",
        ]

        matches = []

        for keyword in keywords:

            context = extract_context(
                container,
                keyword,
                radius=3000,
            )

            if context:

                print(
                    "Намерено:",
                    keyword,
                )

                matches.append(
                    context
                )

        if matches:

            save_debug(
                f"product_container_{sku}_matches.txt",
                "\n".join(matches),
            )

        # ----------------------------------------------------
        # JSON CANDIDATES
        # ----------------------------------------------------

        json_candidates = []

        scripts = re.findall(
            r'<script[^>]*type=["\']application/json["\'][^>]*>'
            r'(.*?)'
            r'</script>',
            container,
            re.I | re.S,
        )

        json_candidates.extend(
            scripts
        )

        for keyword in [
            "quantity",
            "discountedPrice",
            "variants",
            "stores",
        ]:

            positions = [
                m.start()
                for m in re.finditer(
                    re.escape(keyword),
                    container,
                    re.I,
                )
            ]

            for pos in positions[:20]:

                start = max(
                    0,
                    pos - 2000,
                )

                end = min(
                    len(container),
                    pos + 5000,
                )

                chunk = container[
                    start:end
                ]

                json_candidates.append(
                    chunk
                )

        if json_candidates:

            save_debug(
                f"product_container_{sku}_json_candidates.txt",
                "\n\n"
                + (
                    "=" * 80
                    + "\n"
                ).join(
                    json_candidates
                ),
            )

            print(
                "JSON кандидати:",
                len(json_candidates),
            )

        # ----------------------------------------------------
        # ВСИЧКИ ЧИСЛА
        # ----------------------------------------------------

        number_matches = re.findall(
            r'\b\d+(?:\.\d+)?\b',
            container,
        )

        unique_numbers = list(
            dict.fromkeys(
                number_matches
            )
        )

        save_debug(
            f"product_container_{sku}_numbers.txt",
            "\n".join(
                unique_numbers
            ),
        )

        print(
            "Уникални числа в контейнера:",
            len(unique_numbers),
        )

        # ----------------------------------------------------
        # ИЗВЕСТНИ VARIANT IDs
        # ----------------------------------------------------

        known_variants = [
            "8617",
            "8618",
        ]

        for variant_id in known_variants:

            if variant_id in container:

                print(
                    "!!! НАМЕРЕН VARIANT ID:",
                    variant_id,
                )

                context = extract_context(
                    container,
                    variant_id,
                    radius=5000,
                )

                save_debug(
                    f"variant_{variant_id}_context_{sku}.txt",
                    context,
                )

        # ----------------------------------------------------
        # QUANTITY
        # ----------------------------------------------------

        quantity_positions = [
            m.start()
            for m in re.finditer(
                "quantity",
                container,
                re.I,
            )
        ]

        print(
            "Количество 'quantity' срещания:",
            len(quantity_positions),
        )

        for q_index, pos in enumerate(
            quantity_positions[:20],
            1,
        ):

            start = max(
                0,
                pos - 1000,
            )

            end = min(
                len(container),
                pos + 3000,
            )

            save_debug(
                f"quantity_{sku}_{q_index}.txt",
                container[
                    start:end
                ],
            )

        return container

    print(
        "Не е намерен product container за:",
        sku,
    )

    return None


# ============================================================
# API SEARCH PARAMETER TESTS
# ============================================================

def test_api_search_variants(
    session,
    sku,
):

    print()
    print(
        "=" * 60
    )
    print(
        "API SEARCH PARAMETER TESTS"
    )
    print(
        "=" * 60
    )

    base_url = (
        BASE_URL
        + "/api/search"
    )

    tests = {
        "base": {},

        "term_sku": {
            "term": sku,
        },

        "term_variant": {
            "term": f"{sku}",
            "variant": sku,
        },

        "term_product": {
            "term": sku,
            "product": sku,
        },

        "term_id": {
            "term": sku,
            "id": sku,
        },

        "term_page": {
            "term": sku,
            "page": 1,
        },

        "term_limit": {
            "term": sku,
            "limit": 100,
        },

        "term_sku_product": {
            "term": sku,
            "sku": sku,
            "product": sku,
        },

        "term_variant_product": {
            "term": sku,
            "variant": sku,
            "product": sku,
        },
    }

    summary = []

    for name, params in tests.items():

        try:

            response = session.get(
                base_url,
                params=params,
                timeout=30,
            )

            text = response.text

            content_type = (
                response.headers.get(
                    "Content-Type",
                    "",
                )
            )

            print(
                f"   {name}: "
                f"HTTP {response.status_code}, "
                f"{len(text):,} bytes, "
                f"{content_type}"
            )

            filename = (
                f"api_search_tests/"
                f"{sku}_{name}.txt"
            )

            save_debug(
                filename,
                text,
            )

            # ----------------------------------------------
            # Exact known values
            # ----------------------------------------------

            interesting = [
                sku,
                "946537",
                "946534",
                "8617",
                "8618",
                "3809909465340",
                "variant",
                "variants",
                "quantity",
                "price",
                "stores",
                "discountedPrice",
                "maxQuantityByStores",
            ]

            found = []

            for item in interesting:

                if re.search(
                    re.escape(item),
                    text,
                    re.I,
                ):

                    found.append(
                        item
                    )

            print(
                "      Interesting:",
                ", ".join(found)
                if found
                else "NONE",
            )

            # ----------------------------------------------
            # Exact contexts
            # ----------------------------------------------

            contexts = []

            exact_values = [
                sku,
                "946537",
                "946534",
                "8617",
                "8618",
                "3809909465340",
            ]

            for value in exact_values:

                context = extract_context(
                    text,
                    value,
                    radius=3000,
                )

                if context:

                    contexts.append(
                        context
                    )

            if contexts:

                save_debug(
                    f"api_search_tests/"
                    f"{sku}_{name}_exact_matches.txt",
                    "\n".join(
                        contexts
                    ),
                )

            summary.append(
                {
                    "test": name,
                    "status": response.status_code,
                    "size": len(text),
                    "content_type": content_type,
                    "found": found,
                }
            )

        except Exception as e:

            print(
                f"   {name}: ERROR {repr(e)}"
            )

            summary.append(
                {
                    "test": name,
                    "error": repr(e),
                }
            )

    save_debug(
        f"api_search_tests/"
        f"{sku}_summary.json",
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
    )

    return summary


# ============================================================
# TYPESENSE
# ============================================================

def test_typesense_endpoint(
    session,
    sku,
):

    print()
    print(
        "=" * 60
    )
    print(
        "TYPESENSE TESTS"
    )
    print(
        "=" * 60
    )

    url = (
        BASE_URL
        + "/search-json-typesense"
    )

    tests = [
        {
            "q": sku,
        },
        {
            "term": sku,
        },
        {
            "query": sku,
        },
        {
            "q": sku,
            "query_by": "name",
        },
        {
            "q": sku,
            "query_by": "*",
        },
    ]

    results = []

    for index, params in enumerate(
        tests,
        1,
    ):

        try:

            response = session.get(
                url,
                params=params,
                timeout=30,
            )

            print(
                f"   Test {index}: "
                f"HTTP {response.status_code}, "
                f"{len(response.text):,} bytes"
            )

            filename = (
                f"typesense_{sku}_"
                f"{index}.txt"
            )

            save_debug(
                filename,
                response.text,
            )

            results.append(
                {
                    "params": params,
                    "status": response.status_code,
                    "size": len(response.text),
                }
            )

        except Exception as e:

            print(
                "   ❌ Typesense error:",
                repr(e),
            )

            results.append(
                {
                    "params": params,
                    "error": repr(e),
                }
            )

    save_debug(
        f"typesense_{sku}_summary.json",
        json.dumps(
            results,
            ensure_ascii=False,
            indent=2,
        ),
    )

    return results


# ============================================================
# PRODUCT PAGE
# ============================================================

def get_product_page(
    session,
    product_url,
    sku=None,
):

    if not product_url:
        return None

    try:

        response = session.get(
            product_url,
            timeout=30,
        )

        print(
            f"   🌐 Product page → "
            f"HTTP {response.status_code}, "
            f"{len(response.text):,} bytes"
        )

        if sku:

            save_debug(
                f"product_page_{sku}.html",
                response.text,
            )

        return response.text

    except Exception as e:

        print(
            "   ❌ Product page error:",
            repr(e),
        )

        return None


# ============================================================
# PRODUCT PAGE SCAN
# ============================================================

def scan_product_page(
    html,
    sku,
):

    if not html:
        return

    print()
    print(
        "=" * 60
    )
    print(
        "PRODUCT PAGE SCAN"
    )
    print(
        "=" * 60
    )

    keywords = [
        sku,
        "variants",
        "variant",
        "quantity",
        "price",
        "discountedPrice",
        "discountedRetailPrice",
        "traderPrice",
        "stores",
        "maxQuantity",
        "maxQuantityByStores",
        "8617",
        "8618",
        "946534",
        "946537",
        "3809909465340",
        "get-serialize-product",
        "getProductSerializeUrl",
        "addToCartUrl",
    ]

    all_matches = []

    for keyword in keywords:

        context = extract_context(
            html,
            keyword,
            radius=3000,
        )

        if context:

            print(
                "   Found:",
                keyword,
            )

            all_matches.append(
                context
            )

    if all_matches:

        save_debug(
            f"product_page_{sku}_matches.txt",
            "\n".join(
                all_matches
            ),
        )

    # --------------------------------------------------------
    # Exact variant IDs
    # --------------------------------------------------------

    for variant_id in [
        "8617",
        "8618",
    ]:

        if variant_id in html:

            print(
                "   !!! Variant ID found:",
                variant_id,
            )

            context = extract_context(
                html,
                variant_id,
                radius=5000,
            )

            save_debug(
                f"product_page_{sku}_variant_"
                f"{variant_id}.txt",
                context,
            )


# ============================================================
# JAVASCRIPT URLS
# ============================================================

def extract_javascript_urls(
    html
):

    if not html:
        return []

    urls = re.findall(
        r'<script[^>]+src=["\']([^"\']+)["\']',
        html,
        re.I,
    )

    result = []

    for url in urls:

        full_url = urljoin(
            BASE_URL,
            url,
        )

        if full_url not in result:

            result.append(
                full_url
            )

    return result


# ============================================================
# JAVASCRIPT SCAN
# ============================================================

def scan_javascript(
    session,
    html,
):

    print()
    print(
        "=" * 60
    )
    print(
        "JAVASCRIPT SCAN"
    )
    print(
        "=" * 60
    )

    urls = extract_javascript_urls(
        html
    )

    print(
        "JavaScript URLs:",
        len(urls),
    )

    save_debug(
        "javascript_urls.txt",
        "\n".join(urls),
    )

    keywords = [
        "search-json-typesense",
        "Typesense",
        "typesense",
        "query_by",
        "queryBy",
        "search-url",
        "searchUrl",
        "autocomplete",
        "get-serialize-product",
        "getProductSerializeUrl",
        "addToCartUrl",
        "discountedPrice",
        "quantity",
        "variants",
    ]

    all_matches = []

    for index, url in enumerate(
        urls,
        1,
    ):

        print(
            f"   JS {index}/{len(urls)}:",
            url,
        )

        try:

            response = session.get(
                url,
                timeout=30,
            )

            print(
                "      HTTP",
                response.status_code,
                "|",
                len(response.text),
                "bytes",
            )

            js_text = response.text

            save_debug(
                f"js_{index}.js",
                js_text,
            )

            for keyword in keywords:

                context = extract_context(
                    js_text,
                    keyword,
                    radius=2500,
                )

                if context:

                    print(
                        "      Found:",
                        keyword,
                    )

                    all_matches.append(
                        f"\n\nURL: {url}\n"
                        f"KEYWORD: {keyword}\n"
                        f"{context}"
                    )

                    save_debug(
                        f"js_{index}_"
                        f"matches.txt",
                        (
                            extract_context(
                                js_text,
                                keyword,
                                radius=5000,
                            )
                        ),
                    )

        except Exception as e:

            print(
                "      ERROR:",
                repr(e),
            )

    if all_matches:

        save_debug(
            "ALL_JAVASCRIPT_MATCHES.txt",
            "\n".join(
                all_matches
            ),
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print(
        "=" * 70
    )
    print(
        "FILSTAR DIAGNOSTIC SCRAPER"
    )
    print(
        "=" * 70
    )

    init_debug_folder()

    skus = read_skus()

    print(
        f"🧾 Общо SKU: {len(skus)}"
    )

    if not skus:
        print(
            "❌ Няма SKU."
        )
        return

    # --------------------------------------------------------
    # Само първите 3 за диагностика
    # --------------------------------------------------------

    test_skus = skus[:3]

    print(
        "🧪 Тестови SKU:",
        ", ".join(test_skus),
    )

    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/139.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "application/xml;q=0.9,"
                "image/avif,"
                "image/webp,"
                "*/*;q=0.8"
            ),
            "Accept-Language":
                "bg-BG,bg;q=0.9,en;q=0.8",
        }
    )

    init_csv()

    # --------------------------------------------------------
    # JS scanner
    # --------------------------------------------------------

    first_html = None

    if test_skus:

        first_html = search_filstar(
            session,
            test_skus[0],
        )

        if first_html:

            scan_javascript(
                session,
                first_html,
            )

    # --------------------------------------------------------
    # SKUs
    # --------------------------------------------------------

    for index, sku in enumerate(
        test_skus,
        1,
    ):

        print()
        print(
            "=" * 70
        )

        print(
            f"SKU {index}/{len(test_skus)}:",
            sku,
        )

        print(
            "=" * 70
        )

        # ----------------------------------------------------
        # Search
        # ----------------------------------------------------

        html = search_filstar(
            session,
            sku,
        )

        if not html:

            save_not_found(
                sku
            )

            continue

        # ----------------------------------------------------
        # Inspect exact product container
        # ----------------------------------------------------

        inspect_product_container(
            html,
            sku,
        )

        # ----------------------------------------------------
        # Product ID
        # ----------------------------------------------------

        product_id = extract_product_id(
            html
        )

        # ----------------------------------------------------
        # Product URL
        # ----------------------------------------------------

        product_url = extract_product_url(
            html,
            sku,
        )

        # ----------------------------------------------------
        # API parameter tests
        # ----------------------------------------------------

        test_api_search_variants(
            session,
            sku,
        )

        # ----------------------------------------------------
        # Typesense
        # ----------------------------------------------------

        test_typesense_endpoint(
            session,
            sku,
        )

        # ----------------------------------------------------
        # Product page
        # ----------------------------------------------------

        if product_url:

            product_html = get_product_page(
                session,
                product_url,
                sku,
            )

            if product_html:

                scan_product_page(
                    product_html,
                    sku,
                )

        # ----------------------------------------------------
        # Serialize endpoint НЕ СЕ ИЗПОЛЗВА
        # ----------------------------------------------------
        #
        # Нарочно не викаме:
        #
        # /get-serialize-product/{product_id}
        #
        # защото вече знаем, че от GitHub Actions
        # връща HTTP 403.
        #
        # ----------------------------------------------------

        save_not_found(
            sku
        )

        time.sleep(
            WAIT
        )

    print()
    print(
        "=" * 70
    )
    print(
        "DIAGNOSTIC FINISHED"
    )
    print(
        "=" * 70
    )

    print(
        "Debug folder:",
        DEBUG_DIR,
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
