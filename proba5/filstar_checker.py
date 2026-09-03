#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
import os
import re
import shutil
import time
from urllib.parse import quote, urljoin

import requests


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SKU_CSV = os.path.join(BASE_DIR, "sku_list_filstar.csv")
RESULT_CSV = os.path.join(BASE_DIR, "results_filstar.csv")
NOT_FOUND_CSV = os.path.join(BASE_DIR, "not_found_filstar.csv")
DEBUG_DIR = os.path.join(BASE_DIR, "debug_html")

BASE_URL = "https://filstar.com"
WAIT = 2

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "application/json;q=0.8,*/*;q=0.7"
    ),
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
    "Referer": "https://filstar.com/",
}

session = requests.Session()
session.headers.update(HEADERS)


def read_skus():
    result = []
    block = False

    with open(SKU_CSV, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            if line.upper() == "SKU":
                continue

            if line == "##":
                block = not block
                continue

            if block:
                continue

            result.append(line)

    return result


def init_debug_folder():
    if os.path.exists(DEBUG_DIR):
        print("Изтривам старата debug папка:", DEBUG_DIR)

        try:
            shutil.rmtree(DEBUG_DIR)
        except Exception as e:
            print("Грешка при изтриване на debug папката:", e)

    os.makedirs(DEBUG_DIR, exist_ok=True)

    print(
        "Създадена е нова debug папка:",
        DEBUG_DIR,
    )


def save_debug(filename, content):
    if content is None:
        return

    filepath = os.path.join(
        DEBUG_DIR,
        filename,
    )

    os.makedirs(
        os.path.dirname(filepath),
        exist_ok=True,
    )

    try:
        with open(
            filepath,
            "w",
            encoding="utf-8",
        ) as f:

            if isinstance(content, str):
                f.write(content)

            else:
                json.dump(
                    content,
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

        print(
            "Debug:",
            filepath,
        )

    except Exception as e:
        print(
            "Грешка при запис на debug:",
            e,
        )


def init_csv():
    with open(
        RESULT_CSV,
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        csv.writer(f).writerow(
            [
                "SKU",
                "Наличност",
                "Бройки",
                "Цена",
            ]
        )

    with open(
        NOT_FOUND_CSV,
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        csv.writer(f).writerow(
            ["SKU"]
        )


def save_result(row):
    with open(
        RESULT_CSV,
        "a",
        newline="",
        encoding="utf-8",
    ) as f:
        csv.writer(f).writerow(row)


def save_not_found(sku):
    with open(
        NOT_FOUND_CSV,
        "a",
        newline="",
        encoding="utf-8",
    ) as f:
        csv.writer(f).writerow(
            [sku]
        )


def search_filstar(sku):
    url = (
        f"{BASE_URL}/api/search"
        f"?term={quote(str(sku))}"
    )

    print(
        "SEARCH:",
        url,
    )

    try:
        r = session.get(
            url,
            timeout=30,
        )

        print(
            "Search HTTP:",
            r.status_code,
        )

        save_debug(
            f"search_{sku}.html",
            r.text,
        )

        if r.status_code != 200:
            print(
                "Search HTTP грешка:",
                r.status_code,
            )
            return None

        return r.text

    except Exception as e:
        print(
            "SEARCH ERROR:",
            e,
        )
        return None


def extract_product_id(html):
    if not html:
        return None

    # Основният и най-надежден вариант:
    # data-product-id="2557"
    patterns = [
        r'data-product-id=["\'](\d+)["\']',
        r'/get-serialize-product/(\d+)',
        r'product.?id.?[:="\']+(\d+)',
    ]

    ids = []

    for pattern in patterns:
        ids.extend(
            re.findall(
                pattern,
                html,
                re.I,
            )
        )

    ids = list(
        dict.fromkeys(ids)
    )

    print(
        "ID кандидати:",
        ids,
    )

    return ids[0] if ids else None


def extract_product_url(html, sku):
    """
    Намира product-item-wapper контейнера, в който се намира SKU,
    и след това взема вътрешния product link.

    Това е важно, защото старият метод търсеше произволен href
    около SKU и можеше да върне manifest.json или друг служебен URL.
    """

    if not html:
        return None

    sku = str(sku)

    # Търсим всички product-item-wapper контейнери.
    containers = re.findall(
        r'<div[^>]*class=["\'][^"\']*product-item-wapper[^"\']*["\'][^>]*>'
        r'.*?'
        r'</div>\s*</div>\s*</div>',
        html,
        re.I | re.S,
    )

    print(
        "Намерени product-item-wapper контейнери:",
        len(containers),
    )

    # Първо търсим контейнер, който съдържа SKU.
    for container in containers:

        if sku not in container:
            continue

        print(
            "Намерено SKU в product контейнер:",
            sku,
        )

        # Вземаме href от link към продукта.
        hrefs = re.findall(
            r'<a[^>]+href=["\']([^"\']+)["\']',
            container,
            re.I,
        )

        for href in hrefs:
            href = href.strip()

            if not href:
                continue

            # Изключваме служебни URL-и.
            if (
                "/api/" in href
                or "/get-serialize-product/" in href
                or href.startswith("#")
                or href.startswith("javascript:")
            ):
                continue

            full_url = urljoin(
                BASE_URL,
                href,
            )

            # Търсим нормален продукт URL.
            if (
                full_url.startswith(BASE_URL)
                and full_url.rstrip("/") != BASE_URL
                and "manifest.json" not in full_url
                and "/search" not in full_url
                and "/cart" not in full_url
            ):
                print(
                    "Product URL намерен:",
                    full_url,
                )

                return full_url

    # Резервен метод:
    # намираме data-product-id и търсим href непосредствено
    # в същия по-голям HTML блок.
    sku_pos = html.find(sku)

    if sku_pos != -1:

        start = max(
            0,
            sku_pos - 10000,
        )

        end = min(
            len(html),
            sku_pos + 10000,
        )

        nearby = html[start:end]

        hrefs = re.findall(
            r'<a[^>]+href=["\']([^"\']+)["\']',
            nearby,
            re.I,
        )

        for href in hrefs:
            href = href.strip()

            full_url = urljoin(
                BASE_URL,
                href,
            )

            if (
                full_url.startswith(BASE_URL)
                and full_url.rstrip("/") != BASE_URL
                and "manifest.json" not in full_url
                and "/api/" not in full_url
                and "/search" not in full_url
                and "/cart" not in full_url
                and "/get-serialize-product/" not in full_url
            ):
                print(
                    "Product URL намерен чрез fallback:",
                    full_url,
                )

                return full_url

    return None


def extract_all_urls(html):
    if not html:
        return []

    urls = []

    hrefs = re.findall(
        r'href=["\']([^"\']+)["\']',
        html,
        re.I,
    )

    for href in hrefs:

        full_url = urljoin(
            BASE_URL,
            href,
        )

        if full_url.startswith(BASE_URL):

            if full_url not in urls:
                urls.append(full_url)

    return urls


def extract_context(
    text,
    keyword,
    radius=2000,
):
    if not text:
        return ""

    lower_text = text.lower()
    lower_keyword = keyword.lower()

    positions = []
    start = 0

    while True:

        pos = lower_text.find(
            lower_keyword,
            start,
        )

        if pos == -1:
            break

        positions.append(pos)

        start = (
            pos
            + len(lower_keyword)
        )

    if not positions:
        return ""

    chunks = []

    for index, pos in enumerate(
        positions[:30],
        1,
    ):

        chunk_start = max(
            0,
            pos - radius,
        )

        chunk_end = min(
            len(text),
            pos
            + len(keyword)
            + radius,
        )

        chunks.append(
            "\n\n"
            + "=" * 80
            + f"\nMATCH #{index}: {keyword}\n"
            + "=" * 80
            + "\n"
            + text[
                chunk_start:chunk_end
            ]
        )

    return "".join(chunks)


def test_api_search_variants(sku):
    """
    Тества различни параметри към публичния /api/search endpoint.

    Цел:
    Да проверим дали API-то може да върне информация за конкретен
    variant, SKU, product ID или други данни, когато се подадат
    допълнителни параметри.
    """

    print()
    print("=" * 60)
    print("TEST API SEARCH VARIANTS")
    print("=" * 60)

    endpoint = (
        f"{BASE_URL}/api/search"
    )

    sku = str(sku)

    tests = [
        (
            "base",
            {
                "term": sku,
            },
        ),
        (
            "term_sku",
            {
                "term": sku,
                "sku": sku,
            },
        ),
        (
            "term_variant",
            {
                "term": sku,
                "variant": sku,
            },
        ),
        (
            "term_product",
            {
                "term": sku,
                "product": "2557",
            },
        ),
        (
            "term_id",
            {
                "term": sku,
                "id": "2557",
            },
        ),
        (
            "term_page",
            {
                "term": sku,
                "page": "1",
            },
        ),
        (
            "term_limit",
            {
                "term": sku,
                "limit": "100",
            },
        ),
        (
            "term_sku_product",
            {
                "term": sku,
                "sku": sku,
                "product": "2557",
            },
        ),
        (
            "term_variant_product",
            {
                "term": sku,
                "variant": sku,
                "product": "2557",
            },
        ),
    ]

    summary = []

    test_dir = os.path.join(
        DEBUG_DIR,
        "api_search_tests",
    )

    os.makedirs(
        test_dir,
        exist_ok=True,
    )

    interesting_keywords = [
        sku,
        "2557",
        "8617",
        "8618",
        "variants",
        "variant",
        "quantity",
        "discountedPrice",
        "discountedRetailPrice",
        "price",
        "stores",
        "maxQuantity",
        "sku",
    ]

    for test_name, params in tests:

        print()
        print(
            "-" * 60
        )

        print(
            "TEST:",
            test_name,
        )

        print(
            "PARAMS:",
            params,
        )

        try:

            headers = {
                "User-Agent": HEADERS[
                    "User-Agent"
                ],
                "Accept": (
                    "application/json,"
                    "text/plain,"
                    "*/*"
                ),
                "Accept-Language": (
                    HEADERS[
                        "Accept-Language"
                    ]
                ),
                "Referer": (
                    BASE_URL + "/"
                ),
                "X-Requested-With": (
                    "XMLHttpRequest"
                ),
            }

            r = session.get(
                endpoint,
                params=params,
                headers=headers,
                timeout=30,
            )

            print(
                "HTTP:",
                r.status_code,
            )

            print(
                "URL:",
                r.url,
            )

            print(
                "Content-Type:",
                r.headers.get(
                    "Content-Type",
                    "",
                ),
            )

            print(
                "Размер:",
                len(r.text),
                "bytes",
            )

            info = {
                "test": test_name,
                "params": params,
                "url": r.url,
                "status": r.status_code,
                "content_type": r.headers.get(
                    "Content-Type",
                    "",
                ),
                "length": len(r.text),
            }

            # Запазваме целия raw response.
            save_debug(
                os.path.join(
                    "api_search_tests",
                    f"{sku}_{test_name}.txt",
                ),
                (
                    f"URL: {r.url}\n"
                    f"HTTP: {r.status_code}\n"
                    f"Content-Type: "
                    f"{r.headers.get('Content-Type', '')}\n"
                    f"Size: {len(r.text)}\n\n"
                    f"{r.text}"
                ),
            )

            # Търсим интересни полета в raw response.
            response_text = r.text

            found_keywords = []

            for keyword in interesting_keywords:

                if (
                    keyword.lower()
                    in response_text.lower()
                ):
                    found_keywords.append(
                        keyword
                    )

            info[
                "interesting_keywords"
            ] = found_keywords

            print(
                "Интересни полета:",
                found_keywords,
            )

            # Ако е JSON, записваме и структурираната версия.
            try:

                data = r.json()

                info["json"] = True
                info["json_type"] = (
                    type(data).__name__
                )

                save_debug(
                    os.path.join(
                        "api_search_tests",
                        f"{sku}_{test_name}.json",
                    ),
                    data,
                )

                serialized = json.dumps(
                    data,
                    ensure_ascii=False,
                )

                info[
                    "sku_found"
                ] = sku in serialized

                info[
                    "parent_id_found"
                ] = "2557" in serialized

                info[
                    "variant_8617_found"
                ] = "8617" in serialized

                info[
                    "variant_8618_found"
                ] = "8618" in serialized

                info[
                    "quantity_found"
                ] = (
                    "quantity"
                    in serialized.lower()
                )

                info[
                    "discounted_price_found"
                ] = (
                    "discountedPrice"
                    in serialized
                )

                print(
                    "JSON:",
                    type(data).__name__,
                )

                print(
                    "SKU намерено:",
                    info["sku_found"],
                )

                print(
                    "Product 2557:",
                    info[
                        "parent_id_found"
                    ],
                )

                print(
                    "Variant 8617:",
                    info[
                        "variant_8617_found"
                    ],
                )

                print(
                    "Variant 8618:",
                    info[
                        "variant_8618_found"
                    ],
                )

                print(
                    "Quantity:",
                    info[
                        "quantity_found"
                    ],
                )

                print(
                    "discountedPrice:",
                    info[
                        "discounted_price_found"
                    ],
                )

            except Exception as e:

                info["json"] = False
                info["json_error"] = str(e)

                print(
                    "Не е JSON:",
                    e,
                )

            summary.append(
                info
            )

        except Exception as e:

            print(
                "API SEARCH ERROR:",
                e,
            )

            summary.append(
                {
                    "test": test_name,
                    "params": params,
                    "error": str(e),
                }
            )

        time.sleep(1)

    save_debug(
        f"api_search_summary_{sku}.json",
        summary,
    )


def test_typesense_endpoint(sku):
    print()
    print("=" * 60)
    print("TEST SEARCH-JSON-TYPESENSE")
    print("=" * 60)

    endpoint = (
        f"{BASE_URL}/search-json-typesense"
    )

    tests = [
        (
            "q",
            {
                "q": str(sku),
            },
        ),
        (
            "term",
            {
                "term": str(sku),
            },
        ),
        (
            "query",
            {
                "query": str(sku),
            },
        ),
        (
            "q_query_by",
            {
                "q": str(sku),
                "query_by": "sku,name",
            },
        ),
        (
            "q_query_by_all",
            {
                "q": str(sku),
                "query_by": "*",
            },
        ),
    ]

    summary = []

    for test_name, params in tests:

        print()
        print(
            "TEST:",
            test_name,
        )

        print(
            "PARAMS:",
            params,
        )

        try:

            headers = {
                "User-Agent": HEADERS[
                    "User-Agent"
                ],
                "Accept": (
                    "application/json,"
                    "text/plain,*/*"
                ),
                "Accept-Language": (
                    HEADERS[
                        "Accept-Language"
                    ]
                ),
                "Referer": BASE_URL + "/",
                "X-Requested-With": (
                    "XMLHttpRequest"
                ),
            }

            r = session.get(
                endpoint,
                params=params,
                headers=headers,
                timeout=30,
            )

            print(
                "HTTP:",
                r.status_code,
            )

            print(
                "Content-Type:",
                r.headers.get(
                    "Content-Type",
                    "",
                ),
            )

            print(
                "Размер:",
                len(r.text),
                "bytes",
            )

            info = {
                "test": test_name,
                "params": params,
                "url": r.url,
                "status": r.status_code,
                "content_type": r.headers.get(
                    "Content-Type",
                    "",
                ),
                "length": len(r.text),
            }

            try:

                data = r.json()

                save_debug(
                    f"typesense_{sku}_{test_name}.json",
                    data,
                )

                serialized = json.dumps(
                    data,
                    ensure_ascii=False,
                )

                found = (
                    str(sku)
                    in serialized
                )

                info[
                    "sku_found"
                ] = found

                print(
                    "JSON:",
                    type(data).__name__,
                )

                print(
                    "SKU намерено:",
                    found,
                )

            except Exception as e:

                info[
                    "json_error"
                ] = str(e)

                save_debug(
                    f"typesense_{sku}_{test_name}.txt",
                    (
                        f"URL: {r.url}\n"
                        f"HTTP: {r.status_code}\n"
                        f"Content-Type: "
                        f"{r.headers.get('Content-Type', '')}\n"
                        f"Size: {len(r.text)}\n\n"
                        f"{r.text}"
                    ),
                )

                print(
                    "Не е JSON:",
                    e,
                )

            summary.append(
                info
            )

        except Exception as e:

            print(
                "TYPESENSE ERROR:",
                e,
            )

            summary.append(
                {
                    "test": test_name,
                    "params": params,
                    "error": str(e),
                }
            )

    save_debug(
        f"typesense_summary_{sku}.json",
        summary,
    )


def get_product_page(
    product_url,
    sku,
):
    if not product_url:

        print(
            "Няма Product URL."
        )

        return None

    print()
    print(
        "PRODUCT PAGE:",
        product_url,
    )

    try:

        r = session.get(
            product_url,
            timeout=30,
        )

        print(
            "Product HTTP:",
            r.status_code,
        )

        print(
            "Размер:",
            len(r.text),
            "bytes",
        )

        save_debug(
            f"product_{sku}.html",
            r.text,
        )

        if r.status_code != 200:

            print(
                "Product page HTTP грешка:",
                r.status_code,
            )

            return None

        return r.text

    except Exception as e:

        print(
            "PRODUCT PAGE ERROR:",
            e,
        )

        return None


def scan_product_page(
    html,
    sku,
):
    if not html:
        return

    print()
    print("=" * 60)
    print("SCAN PRODUCT PAGE")
    print("=" * 60)

    keywords = [
        str(sku),
        "variants",
        "variant",
        "quantity",
        "discountedPrice",
        "discountedRetailPrice",
        "traderPrice",
        "stores",
        "maxQuantity",
        "data-product-id",
        "data-product-variant",
        "add-variant-to-cart",
        "getProductSerializeUrl",
        "get-serialize-product",
        "search-json-typesense",
    ]

    matches = []

    for keyword in keywords:

        context = extract_context(
            html,
            keyword,
            radius=2500,
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
            f"product_{sku}_matches.txt",
            "\n".join(matches),
        )

    data_attributes = re.findall(
        r'data-[a-zA-Z0-9_-]+=["\'][^"\']*["\']',
        html,
        re.I,
    )

    if data_attributes:

        unique_attributes = list(
            dict.fromkeys(
                data_attributes
            )
        )

        save_debug(
            f"product_{sku}_data_attributes.txt",
            "\n".join(
                unique_attributes
            ),
        )

        print(
            "Data attributes:",
            len(unique_attributes),
        )

    json_blocks = re.findall(
        r'<script[^>]*type=["\']application/json["\'][^>]*>'
        r'(.*?)'
        r'</script>',
        html,
        re.I | re.S,
    )

    print(
        "JSON script блокове:",
        len(json_blocks),
    )

    for index, block in enumerate(
        json_blocks,
        1,
    ):

        save_debug(
            f"product_{sku}_json_{index}.txt",
            block,
        )

    scripts = re.findall(
        r'<script[^>]*>(.*?)</script>',
        html,
        re.I | re.S,
    )

    for index, script in enumerate(
        scripts,
        1,
    ):

        if any(
            keyword.lower()
            in script.lower()
            for keyword in keywords
        ):

            save_debug(
                f"product_{sku}_inline_script_{index}.js",
                script,
            )


def extract_javascript_urls(html):
    if not html:
        return []

    urls = []

    patterns = [
        r'<script[^>]+src=["\']([^"\']+)["\']',
        r'<script[^>]+src=([^ >]+)',
    ]

    for pattern in patterns:

        for src in re.findall(
            pattern,
            html,
            re.I,
        ):

            src = (
                src
                .strip()
                .strip("\"'")
            )

            if not src:
                continue

            full_url = urljoin(
                BASE_URL + "/",
                src,
            )

            if full_url not in urls:
                urls.append(
                    full_url
                )

    return urls


def scan_javascript(html):
    print()
    print("=" * 60)
    print("JAVASCRIPT SCANNER")
    print("=" * 60)

    js_urls = extract_javascript_urls(
        html
    )

    print(
        "Намерени JS файлове:",
        len(js_urls),
    )

    save_debug(
        "javascript_urls.txt",
        "\n".join(js_urls),
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
        js_urls,
        1,
    ):

        print()
        print(
            f"JS {index}/{len(js_urls)}"
        )

        print(url)

        try:

            r = session.get(
                url,
                timeout=30,
            )

            print(
                "HTTP:",
                r.status_code,
            )

            if r.status_code != 200:
                continue

            js = r.text

            save_debug(
                f"js_{index}.js",
                js,
            )

            file_matches = []

            for keyword in keywords:

                if (
                    keyword.lower()
                    not in js.lower()
                ):
                    continue

                print(
                    "Намерено:",
                    keyword,
                )

                context = extract_context(
                    js,
                    keyword,
                    radius=2500,
                )

                if context:
                    file_matches.append(
                        context
                    )

            if file_matches:

                save_debug(
                    f"js_{index}_matches.txt",
                    "\n".join(
                        file_matches
                    ),
                )

                all_matches.extend(
                    file_matches
                )

        except Exception as e:

            print(
                "JS ERROR:",
                e,
            )

    if all_matches:

        save_debug(
            "ALL_JAVASCRIPT_MATCHES.txt",
            "\n".join(
                all_matches
            ),
        )


def main():
    init_debug_folder()
    init_csv()

    skus = read_skus()

    print(
        "Общо SKU:",
        len(skus),
    )

    scanner_done = False

    # Диагностично тестваме само
    # първите 3 SKU.
    test_skus = skus[:3]

    print(
        "Диагностичен режим. SKU:",
        test_skus,
    )

    for sku in test_skus:

        print()
        print("=" * 60)
        print(
            "SKU:",
            sku,
        )
        print("=" * 60)

        html = search_filstar(
            sku
        )

        if not html:

            save_not_found(
                sku
            )

            continue

        context = extract_context(
            html,
            str(sku),
            radius=3000,
        )

        if context:

            save_debug(
                f"search_{sku}_sku_context.txt",
                context,
            )

        if not scanner_done:

            scan_javascript(
                html
            )

            scanner_done = True

        product_id = extract_product_id(
            html
        )

        if product_id:

            print(
                "Product ID:",
                product_id,
            )

        else:

            print(
                "Product ID не е намерено."
            )

        product_url = extract_product_url(
            html,
            sku,
        )

        if product_url:

            print(
                "Product URL:",
                product_url,
            )

        else:

            print(
                "Product URL не е намерено."
            )

        save_debug(
            f"search_{sku}_all_urls.txt",
            "\n".join(
                extract_all_urls(
                    html
                )
            ),
        )

        # --------------------------------------------------
        # НОВ ТЕСТ
        # Публичният /api/search endpoint
        # с различни параметри.
        # --------------------------------------------------

        test_api_search_variants(
            sku
        )

        # --------------------------------------------------
        # Старият Typesense тест
        # --------------------------------------------------

        test_typesense_endpoint(
            sku
        )

        # --------------------------------------------------
        # Публичната продуктова страница
        # --------------------------------------------------

        product_html = get_product_page(
            product_url,
            sku,
        )

        if product_html:

            scan_product_page(
                product_html,
                sku,
            )

        save_not_found(
            sku
        )

        time.sleep(
            WAIT
        )

    print()
    print("=" * 60)
    print(
        "ДИАГНОСТИКАТА ПРИКЛЮЧИ"
    )
    print("=" * 60)

    print(
        "Debug:",
        DEBUG_DIR,
    )

    print(
        "Results:",
        RESULT_CSV,
    )

    print(
        "Not found:",
        NOT_FOUND_CSV,
    )

    print()
    print(
        "Тествахме само първите 3 SKU."
    )

    print(
        "/get-serialize-product/ НЕ Е ИЗПОЛЗВАН."
    )

    print(
        "/search-json-typesense е тестван."
    )

    print(
        "/api/search е тестван с различни параметри."
    )

    print(
        "Продуктовите страници са сканирани."
    )


if __name__ == "__main__":
    main()
