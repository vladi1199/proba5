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
# READ SKUS
# ============================================================

def read_skus():

    skus = []

    in_comment = False

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

            # ------------------------------------------------
            # Block comments:
            #
            # ##
            # SKU
            # SKU
            # ##
            # ------------------------------------------------

            if sku == "##":

                in_comment = not in_comment

                continue

            if in_comment:
                continue

            skus.append(sku)

    return skus


# ============================================================
# DEBUG FOLDER
# ============================================================

def init_debug_folder():

    if os.path.exists(DEBUG_DIR):

        shutil.rmtree(
            DEBUG_DIR
        )

    os.makedirs(
        DEBUG_DIR,
        exist_ok=True,
    )


def save_debug(
    filename,
    content,
):

    path = os.path.join(
        DEBUG_DIR,
        filename,
    )

    folder = os.path.dirname(
        path
    )

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

        if isinstance(
            content,
            str,
        ):

            f.write(
                content
            )

        else:

            f.write(
                str(content)
            )


# ============================================================
# RESULT CSV
# ============================================================

def init_csv():

    with open(
        RESULTS_FILE,
        "w",
        encoding="utf-8",
        newline="",
    ) as f:

        writer = csv.writer(
            f
        )

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

        writer = csv.writer(
            f
        )

        writer.writerow(
            [
                sku,
                availability,
                quantity,
                price,
            ]
        )


def save_not_found(
    sku
):

    with open(
        NOT_FOUND_FILE,
        "a",
        encoding="utf-8",
        newline="",
    ) as f:

        writer = csv.writer(
            f
        )

        writer.writerow(
            [sku]
        )


# ============================================================
# REQUEST SESSION
# ============================================================

def create_session():

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

            "Connection":
                "keep-alive",
        }
    )

    return session


# ============================================================
# API SEARCH
# ============================================================

def search_filstar(
    session,
    sku,
):

    url = (
        BASE_URL
        + "/api/search?term="
        + quote(
            str(sku)
        )
    )

    try:

        response = session.get(
            url,
            timeout=30,
        )

        print(
            f"   🔎 /api/search?term={sku} "
            f"→ HTTP {response.status_code}"
        )

        print(
            f"   Content-Type: "
            f"{response.headers.get('Content-Type', '')}"
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

def extract_product_id(
    html
):

    if not html:
        return None

    patterns = [

        r'data-product-id=["\'](\d+)["\']',

        r'"productId"\s*:\s*"?(\d+)',

        r'"product_id"\s*:\s*"?(\d+)',

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.I,
        )

        if match:

            product_id = match.group(
                1
            )

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
# FIND PRODUCT CONTAINERS
# ============================================================

def find_product_container_starts(
    html
):

    return list(
        re.finditer(
            r'<div\b[^>]*class=["\'][^"\']*product-item-wapper[^"\']*["\'][^>]*>',
            html,
            re.I,
        )
    )


# ============================================================
# MATCHING DIV END
# ============================================================

def find_matching_div_end(
    text,
    start_pos,
):

    tag_pattern = re.compile(
        r'<(/?)div\b[^>]*>',
        re.I,
    )

    depth = 0

    for match in tag_pattern.finditer(
        text,
        start_pos,
    ):

        tag = match.group(
            0
        )

        # Opening div
        if re.match(
            r'<div\b',
            tag,
            re.I,
        ):

            depth += 1

        # Closing div
        else:

            depth -= 1

            if depth == 0:

                return match.end()

    return len(text)


# ============================================================
# EXTRACT PRODUCT CONTAINER
# ============================================================

def extract_product_container(
    html,
    sku,
):

    if not html:
        return None

    sku = str(
        sku
    )

    starts = find_product_container_starts(
        html
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

        end_pos = find_matching_div_end(
            html,
            start_pos,
        )

        container = html[
            start_pos:end_pos
        ]

        if sku in container:

            print(
                "Намерен container за SKU:",
                sku,
            )

            print(
                "Container size:",
                len(container),
                "bytes",
            )

            return container

    return None


# ============================================================
# EXTRACT PRODUCT URL
# ============================================================

def extract_product_url(
    html,
    sku,
):

    container = extract_product_container(
        html,
        sku,
    )

    if not container:
        return None

    hrefs = re.findall(
        r'href\s*=\s*(["\'])(.*?)\1',
        container,
        re.I | re.S,
    )

    ignored = (
        "/search",
        "/api/",
        "/cart/",
        "/login",
        "/register",
        "/manifest",
    )

    for _, href in hrefs:

        if not href.startswith(
            "/"
        ):
            continue

        if href.startswith(
            ignored
        ):
            continue

        return urljoin(
            BASE_URL,
            href,
        )

    return None


# ============================================================
# CONTEXT EXTRACTOR
# ============================================================

def extract_context(
    text,
    keyword,
    radius=3000,
):

    if not text:
        return ""

    positions = [
        match.start()
        for match in re.finditer(
            re.escape(
                str(keyword)
            ),
            text,
            re.I,
        )
    ]

    if not positions:
        return ""

    output = []

    for position in positions:

        start = max(
            0,
            position - radius,
        )

        end = min(
            len(text),
            position + radius,
        )

        output.append(
            "\n"
            + "=" * 100
            + "\n"
            + f"KEYWORD: {keyword}\n"
            + f"POSITION: {position}\n"
            + "=" * 100
            + "\n"
            + text[start:end]
        )

    return "\n".join(
        output
    )


# ============================================================
# INSPECT PRODUCT CONTAINER
# ============================================================

def inspect_product_container(
    html,
    sku,
):

    if not html:
        return None

    sku = str(
        sku
    )

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

    container = extract_product_container(
        html,
        sku,
    )

    if not container:

        print(
            "Не е намерен product container за:",
            sku,
        )

        save_debug(
            f"product_container_{sku}_NOT_FOUND.txt",
            (
                f"SKU {sku} не е намерен "
                f"в нито един product-item-wapper.\n"
            ),
        )

        return None

    # --------------------------------------------------------
    # FULL CONTAINER
    # --------------------------------------------------------

    save_debug(
        f"product_container_{sku}.html",
        container,
    )

    # --------------------------------------------------------
    # DATA ATTRIBUTES
    # --------------------------------------------------------

    data_matches = re.findall(
        r'\b(data-[a-zA-Z0-9_-]+)\s*=\s*(["\'])(.*?)\2',
        container,
        re.I | re.S,
    )

    data_output = []

    for name, _, value in data_matches:

        data_output.append(
            f"{name} = {value}"
        )

    save_debug(
        f"product_container_{sku}_data.txt",
        "\n".join(
            data_output
        ),
    )

    print(
        "Data attributes:",
        len(data_output),
    )

    # --------------------------------------------------------
    # HREFS
    # --------------------------------------------------------

    hrefs = re.findall(
        r'href\s*=\s*(["\'])(.*?)\1',
        container,
        re.I | re.S,
    )

    href_output = [
        href
        for _, href in hrefs
    ]

    save_debug(
        f"product_container_{sku}_hrefs.txt",
        "\n".join(
            href_output
        ),
    )

    print(
        "HREF:",
        href_output,
    )

    # --------------------------------------------------------
    # IMAGES
    # --------------------------------------------------------

    images = re.findall(
        r'<img\b[^>]*src\s*=\s*(["\'])(.*?)\1',
        container,
        re.I | re.S,
    )

    image_output = [
        src
        for _, src in images
    ]

    save_debug(
        f"product_container_{sku}_images.txt",
        "\n".join(
            image_output
        ),
    )

    # --------------------------------------------------------
    # ALL KEYWORDS
    # --------------------------------------------------------

    keywords = [
        sku,

        "variant",
        "variants",

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
        "946535",
        "946537",

        "3809909465340",
    ]

    all_matches = []

    for keyword in keywords:

        context = extract_context(
            container,
            keyword,
            radius=4000,
        )

        if not context:
            continue

        print(
            "Намерено:",
            keyword,
        )

        all_matches.append(
            context
        )

    if all_matches:

        save_debug(
            f"product_container_{sku}_matches.txt",
            "\n\n".join(
                all_matches
            ),
        )

    # --------------------------------------------------------
    # EXACT VARIANT IDS
    # --------------------------------------------------------

    variant_results = []

    for variant_id in [
        "8617",
        "8618",
    ]:

        positions = [
            match.start()
            for match in re.finditer(
                re.escape(
                    variant_id
                ),
                container,
            )
        ]

        if positions:

            print(
                "!!! НАМЕРЕН VARIANT ID:",
                variant_id,
            )

            for position in positions:

                start = max(
                    0,
                    position - 5000,
                )

                end = min(
                    len(container),
                    position + 10000,
                )

                variant_results.append(
                    "\n"
                    + "=" * 100
                    + "\n"
                    + f"VARIANT ID: {variant_id}\n"
                    + f"POSITION: {position}\n"
                    + "=" * 100
                    + "\n"
                    + container[start:end]
                )

    if variant_results:

        save_debug(
            f"product_container_{sku}_"
            f"variant_ids.txt",
            "\n".join(
                variant_results
            ),
        )

    # --------------------------------------------------------
    # EXACT KNOWN SKUS
    # --------------------------------------------------------

    sku_results = []

    for exact_sku in [
        "946534",
        "946535",
        "946537",
    ]:

        positions = [
            match.start()
            for match in re.finditer(
                re.escape(
                    exact_sku
                ),
                container,
            )
        ]

        if positions:

            print(
                f"SKU {exact_sku}: "
                f"{len(positions)} occurrence(s)"
            )

            for position in positions:

                start = max(
                    0,
                    position - 5000,
                )

                end = min(
                    len(container),
                    position + 10000,
                )

                sku_results.append(
                    "\n"
                    + "=" * 100
                    + "\n"
                    + f"SKU: {exact_sku}\n"
                    + f"POSITION: {position}\n"
                    + "=" * 100
                    + "\n"
                    + container[start:end]
                )

    if sku_results:

        save_debug(
            f"product_container_{sku}_"
            f"sku_matches.txt",
            "\n".join(
                sku_results
            ),
        )

    # --------------------------------------------------------
    # QUANTITY
    # --------------------------------------------------------

    quantity_positions = [
        match.start()
        for match in re.finditer(
            r'\bquantity\b',
            container,
            re.I,
        )
    ]

    print(
        "Количество 'quantity':",
        len(quantity_positions),
    )

    quantity_results = []

    for position in quantity_positions:

        start = max(
            0,
            position - 5000,
        )

        end = min(
            len(container),
            position + 10000,
        )

        quantity_results.append(
            container[start:end]
        )

    if quantity_results:

        save_debug(
            f"product_container_{sku}_"
            f"quantity.txt",
            "\n\n"
            + (
                "\n\n"
                + "=" * 100
                + "\n\n"
            ).join(
                quantity_results
            ),
        )

    # --------------------------------------------------------
    # PRICE
    # --------------------------------------------------------

    price_positions = [
        match.start()
        for match in re.finditer(
            r'\bprice\b',
            container,
            re.I,
        )
    ]

    print(
        "Количество 'price':",
        len(price_positions),
    )

    price_results = []

    for position in price_positions:

        start = max(
            0,
            position - 5000,
        )

        end = min(
            len(container),
            position + 10000,
        )

        price_results.append(
            container[start:end]
        )

    if price_results:

        save_debug(
            f"product_container_{sku}_"
            f"price.txt",
            "\n\n"
            + (
                "\n\n"
                + "=" * 100
                + "\n\n"
            ).join(
                price_results
            ),
        )

    # --------------------------------------------------------
    # VARIANT
    # --------------------------------------------------------

    variant_positions = [
        match.start()
        for match in re.finditer(
            r'\bvariant\b',
            container,
            re.I,
        )
    ]

    print(
        "Количество 'variant':",
        len(variant_positions),
    )

    variant_contexts = []

    for position in variant_positions:

        start = max(
            0,
            position - 5000,
        )

        end = min(
            len(container),
            position + 10000,
        )

        variant_contexts.append(
            container[start:end]
        )

    if variant_contexts:

        save_debug(
            f"product_container_{sku}_"
            f"variant.txt",
            "\n\n"
            + (
                "\n\n"
                + "=" * 100
                + "\n\n"
            ).join(
                variant_contexts
            ),
        )

    # --------------------------------------------------------
    # JSON SCRIPT TAGS
    # --------------------------------------------------------

    json_scripts = re.findall(
        r'<script[^>]*type=["\']application/json["\'][^>]*>'
        r'(.*?)'
        r'</script>',
        container,
        re.I | re.S,
    )

    if json_scripts:

        print(
            "JSON script blocks:",
            len(json_scripts),
        )

        save_debug(
            f"product_container_{sku}_"
            f"json_scripts.txt",
            "\n\n"
            + (
                "\n\n"
                + "=" * 100
                + "\n\n"
            ).join(
                json_scripts
            ),
        )

    # --------------------------------------------------------
    # VUE / COMPONENT ATTRIBUTES
    # --------------------------------------------------------

    vue_attributes = []

    for pattern in [
        r':([a-zA-Z0-9_-]+)=',
        r'v-([a-zA-Z0-9_-]+)=',
        r'@([a-zA-Z0-9_-]+)=',
    ]:

        found = re.findall(
            pattern,
            container,
            re.I,
        )

        vue_attributes.extend(
            found
        )

    if vue_attributes:

        save_debug(
            f"product_container_{sku}_"
            f"vue_attributes.txt",
            "\n".join(
                dict.fromkeys(
                    vue_attributes
                )
            ),
        )

    # --------------------------------------------------------
    # NUMBERS
    # --------------------------------------------------------

    numbers = re.findall(
        r'\b\d+(?:\.\d+)?\b',
        container,
    )

    unique_numbers = list(
        dict.fromkeys(
            numbers
        )
    )

    save_debug(
        f"product_container_{sku}_"
        f"numbers.txt",
        "\n".join(
            unique_numbers
        ),
    )

    print(
        "Уникални числа:",
        len(unique_numbers),
    )

    # --------------------------------------------------------
    # TEXT ONLY
    # --------------------------------------------------------

    text_only = re.sub(
        r'<[^>]+>',
        " ",
        container,
    )

    text_only = re.sub(
        r'\s+',
        " ",
        text_only,
    ).strip()

    save_debug(
        f"product_container_{sku}_"
        f"text.txt",
        text_only,
    )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    summary = {
        "sku": sku,
        "container_size": len(container),
        "data_attributes": len(data_output),
        "hrefs": href_output,
        "images": image_output,
        "variant_occurrences": len(variant_positions),
        "quantity_occurrences": len(quantity_positions),
        "price_occurrences": len(price_positions),
        "variant_ids_found": [
            variant_id
            for variant_id in [
                "8617",
                "8618",
            ]
            if variant_id in container
        ],
        "known_skus_found": [
            exact_sku
            for exact_sku in [
                "946534",
                "946535",
                "946537",
            ]
            if exact_sku in container
        ],
        "contains_barcode": (
            "3809909465340"
            in container
        ),
        "numbers": unique_numbers,
    }

    save_debug(
        f"product_container_{sku}_"
        f"summary.json",
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
    )

    return container


# ============================================================
# DIRECT API SEARCH TEST
# ============================================================

def test_api_search(
    session,
    sku,
):

    print()
    print(
        "=" * 60
    )
    print(
        "API SEARCH"
    )
    print(
        "=" * 60
    )

    html = search_filstar(
        session,
        sku,
    )

    if not html:
        return None

    # --------------------------------------------------------
    # Exact values in the COMPLETE response
    # --------------------------------------------------------

    exact_values = [
        sku,
        "946534",
        "946535",
        "946537",
        "8617",
        "8618",
        "3809909465340",
    ]

    exact_matches = []

    for value in exact_values:

        context = extract_context(
            html,
            value,
            radius=5000,
        )

        if context:

            print(
                "   Exact match:",
                value,
            )

            exact_matches.append(
                context
            )

    if exact_matches:

        save_debug(
            f"api_search_{sku}_"
            f"exact_matches.txt",
            "\n\n".join(
                exact_matches
            ),
        )

    # --------------------------------------------------------
    # Generic keywords
    # --------------------------------------------------------

    keywords = [
        "variant",
        "variants",
        "quantity",
        "price",
        "discountedPrice",
        "discountedRetailPrice",
        "traderPrice",
        "stores",
        "maxQuantity",
        "maxQuantityByStores",
    ]

    keyword_summary = {}

    for keyword in keywords:

        count = len(
            list(
                re.finditer(
                    re.escape(
                        keyword
                    ),
                    html,
                    re.I,
                )
            )
        )

        keyword_summary[
            keyword
        ] = count

    save_debug(
        f"api_search_{sku}_"
        f"keyword_summary.json",
        json.dumps(
            keyword_summary,
            ensure_ascii=False,
            indent=2,
        ),
    )

    # --------------------------------------------------------
    # Product container
    # --------------------------------------------------------

    container = inspect_product_container(
        html,
        sku,
    )

    # --------------------------------------------------------
    # Product ID
    # --------------------------------------------------------

    product_id = extract_product_id(
        html
    )

    # --------------------------------------------------------
    # Product URL
    # --------------------------------------------------------

    product_url = extract_product_url(
        html,
        sku,
    )

    if product_url:

        print(
            "   🔗 Product URL:",
            product_url,
        )

    else:

        print(
            "   ❌ Product URL not found"
        )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    summary = {
        "sku": sku,
        "response_size": len(html),
        "product_id": product_id,
        "product_url": product_url,
        "container_found": (
            container is not None
        ),
        "container_size": (
            len(container)
            if container
            else 0
        ),
        "keywords": keyword_summary,
    }

    save_debug(
        f"api_search_{sku}_summary.json",
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
    )

    return summary


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

    # --------------------------------------------------------
    # Debug
    # --------------------------------------------------------

    init_debug_folder()

    # --------------------------------------------------------
    # Read SKUs
    # --------------------------------------------------------

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
        ", ".join(
            test_skus
        ),
    )

    # --------------------------------------------------------
    # Session
    # --------------------------------------------------------

    session = create_session()

    # --------------------------------------------------------
    # CSV
    # --------------------------------------------------------

    init_csv()

    # --------------------------------------------------------
    # Not found file
    # --------------------------------------------------------

    with open(
        NOT_FOUND_FILE,
        "w",
        encoding="utf-8",
        newline="",
    ) as f:

        writer = csv.writer(
            f
        )

        writer.writerow(
            ["SKU"]
        )

    # --------------------------------------------------------
    # Process SKUs
    # --------------------------------------------------------

    all_summaries = []

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

        summary = test_api_search(
            session,
            sku,
        )

        if summary:

            all_summaries.append(
                summary
            )

        # ----------------------------------------------------
        # Засега диагностичният режим НЕ записва резултат.
        # ----------------------------------------------------

        save_not_found(
            sku
        )

        # ----------------------------------------------------
        # Пауза
        # ----------------------------------------------------

        if index < len(
            test_skus
        ):

            time.sleep(
                WAIT
            )

    # --------------------------------------------------------
    # Global summary
    # --------------------------------------------------------

    save_debug(
        "GLOBAL_SUMMARY.json",
        json.dumps(
            all_summaries,
            ensure_ascii=False,
            indent=2,
        ),
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

    print()
    print(
        "ВАЖНО:"
    )

    print(
        "Този тест НЕ използва:"
    )

    print(
        " - /get-serialize-product/"
    )

    print(
        " - /search-json-typesense"
    )

    print(
        " - product page"
    )

    print(
        " - browser automation"
    )

    print(
        " - Cloudflare bypass"
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()
