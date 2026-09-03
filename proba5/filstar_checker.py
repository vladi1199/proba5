#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import re
import time
import requests
import shutil
import json


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


SKU_CSV = os.path.join(
    BASE_DIR,
    "sku_list_filstar.csv"
)


RESULT_CSV = os.path.join(
    BASE_DIR,
    "results_filstar.csv"
)


NOT_FOUND_CSV = os.path.join(
    BASE_DIR,
    "not_found_filstar.csv"
)


DEBUG_DIR = os.path.join(
    BASE_DIR,
    "debug_html"
)


BASE_URL = "https://filstar.com"

WAIT = 2


HEADERS = {

    "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36",

    "Accept":
    "text/html,application/xhtml+xml,application/xml;q=0.9,"
    "application/json;q=0.8,*/*;q=0.7",

    "Accept-Language":
    "bg-BG,bg;q=0.9,en;q=0.8",

    "Referer":
    "https://filstar.com/"
}


session = requests.Session()

session.headers.update(
    HEADERS
)


# =========================================================
# READ SKU
# =========================================================

def read_skus():

    result = []

    block = False

    with open(
        SKU_CSV,
        encoding="utf-8-sig"
    ) as f:

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


# =========================================================
# INIT DEBUG FOLDER
# =========================================================

def init_debug_folder():

    if os.path.exists(DEBUG_DIR):

        print(
            "🗑️ Изтривам старата debug папка:",
            DEBUG_DIR
        )

        try:

            shutil.rmtree(
                DEBUG_DIR
            )

        except Exception as e:

            print(
                "⚠️ Грешка при изтриване на debug папката:",
                e
            )


    os.makedirs(
        DEBUG_DIR,
        exist_ok=True
    )

    print(
        "📁 Създадена е нова debug папка:",
        DEBUG_DIR
    )


# =========================================================
# SAVE DEBUG
# =========================================================

def save_debug(
    filename,
    content
):

    if content is None:
        return


    filepath = os.path.join(
        DEBUG_DIR,
        filename
    )


    try:

        with open(
            filepath,
            "w",
            encoding="utf-8"
        ) as f:

            if isinstance(content, str):

                f.write(
                    content
                )

            else:

                json.dump(
                    content,
                    f,
                    ensure_ascii=False,
                    indent=2
                )


        print(
            "💾 Debug:",
            filepath
        )


    except Exception as e:

        print(
            "⚠️ Грешка при запис на debug:",
            e
        )


# =========================================================
# INIT CSV
# =========================================================

def init_csv():

    with open(
        RESULT_CSV,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        csv.writer(f).writerow(
            [
                "SKU",
                "Наличност",
                "Бройки",
                "Цена"
            ]
        )


    with open(
        NOT_FOUND_CSV,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        csv.writer(f).writerow(
            [
                "SKU"
            ]
        )


# =========================================================
# SAVE RESULT
# =========================================================

def save_result(row):

    with open(
        RESULT_CSV,
        "a",
        newline="",
        encoding="utf-8"
    ) as f:

        csv.writer(f).writerow(
            row
        )


# =========================================================
# SAVE NOT FOUND
# =========================================================

def save_not_found(sku):

    with open(
        NOT_FOUND_CSV,
        "a",
        newline="",
        encoding="utf-8"
    ) as f:

        csv.writer(f).writerow(
            [
                sku
            ]
        )


# =========================================================
# SEARCH FILSTAR
# =========================================================

def search_filstar(sku):

    url = (
        f"{BASE_URL}/api/search?term={sku}"
    )


    print(
        "🌐 SEARCH:",
        url
    )


    try:

        r = session.get(
            url,
            timeout=30
        )


        print(
            "🔎 Search HTTP:",
            r.status_code
        )


        html = r.text


        save_debug(
            f"search_{sku}.html",
            html
        )


        if r.status_code != 200:

            print(
                "❌ Search HTTP грешка:",
                r.status_code
            )

            return None


        return html


    except Exception as e:

        print(
            "SEARCH ERROR:",
            e
        )

        return None


# =========================================================
# EXTRACT JAVASCRIPT URLS
# =========================================================

def extract_javascript_urls(html):

    if not html:
        return []


    urls = []


    # -----------------------------------------------------
    # <script src="...">
    # -----------------------------------------------------

    patterns = [

        r'<script[^>]+src=["\']([^"\']+)["\']',

        r'<script[^>]+src=([^ >]+)',

    ]


    for pattern in patterns:

        matches = re.findall(
            pattern,
            html,
            re.I
        )


        for src in matches:

            src = src.strip()

            src = src.strip(
                "\"'"
            )


            if not src:
                continue


            if src.startswith("//"):

                src = "https:" + src


            elif src.startswith("/"):

                src = BASE_URL + src


            elif src.startswith("http://"):

                src = "https://" + src[7:]


            elif not src.startswith("http"):

                src = BASE_URL + "/" + src.lstrip("/")


            if src not in urls:

                urls.append(src)


    return urls


# =========================================================
# FIND TEXT AROUND MATCH
# =========================================================

def extract_context(
    text,
    keyword,
    radius=1200
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
            start
        )


        if pos == -1:
            break


        positions.append(
            pos
        )


        start = pos + len(
            lower_keyword
        )


    if not positions:
        return ""


    chunks = []


    for index, pos in enumerate(
        positions[:20],
        1
    ):

        chunk_start = max(
            0,
            pos - radius
        )


        chunk_end = min(
            len(text),
            pos + len(keyword) + radius
        )


        chunk = text[
            chunk_start:chunk_end
        ]


        chunks.append(
            "\n\n"
            + "=" * 80
            + f"\nMATCH #{index}: {keyword}\n"
            + "=" * 80
            + "\n"
            + chunk
        )


    return "".join(
        chunks
    )


# =========================================================
# SCAN JAVASCRIPT
# =========================================================

def scan_javascript(
    html
):

    print()
    print(
        "================================================"
    )
    print(
        "🔬 JAVASCRIPT SCANNER"
    )
    print(
        "================================================"
    )


    # -----------------------------------------------------
    # Извличаме всички JS файлове
    # -----------------------------------------------------

    js_urls = extract_javascript_urls(
        html
    )


    print(
        "📜 Намерени JS файлове:",
        len(js_urls)
    )


    for index, url in enumerate(
        js_urls,
        1
    ):

        print(
            f"   {index}. {url}"
        )


    save_debug(
        "javascript_urls.txt",
        "\n".join(js_urls)
    )


    # -----------------------------------------------------
    # Ключови думи
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # Сканираме JS файловете
    # -----------------------------------------------------

    for index, url in enumerate(
        js_urls,
        1
    ):

        print()
        print(
            "------------------------------------------------"
        )

        print(
            f"📥 JS {index}/{len(js_urls)}"
        )

        print(
            url
        )


        try:

            r = session.get(
                url,
                timeout=30
            )


            print(
                "   HTTP:",
                r.status_code
            )


            if r.status_code != 200:

                print(
                    "   ❌ JS недостъпен"
                )

                continue


            js = r.text


            filename = (
                f"js_{index}.js"
            )


            save_debug(
                filename,
                js
            )


            print(
                "   📦 Размер:",
                len(js),
                "bytes"
            )


            file_matches = []


            for keyword in keywords:

                if keyword.lower() not in js.lower():

                    continue


                print(
                    "   🎯 НАМЕРЕНО:",
                    keyword
                )


                context = extract_context(
                    js,
                    keyword
                )


                if context:

                    file_matches.append(
                        context
                    )


            if file_matches:

                result_filename = (
                    f"js_{index}_matches.txt"
                )


                save_debug(
                    result_filename,
                    "\n".join(file_matches)
                )


                all_matches.extend(
                    file_matches
                )


        except Exception as e:

            print(
                "   ❌ JS ERROR:",
                e
            )


    # -----------------------------------------------------
    # Сканираме и самия HTML
    # -----------------------------------------------------

    print()
    print(
        "🔎 Проверявам и HTML-а за endpoint-и..."
    )


    html_matches = []


    for keyword in keywords:

        if keyword.lower() not in html.lower():

            continue


        print(
            "🎯 HTML НАМЕРЕНО:",
            keyword
        )


        context = extract_context(
            html,
            keyword
        )


        if context:

            html_matches.append(
                context
            )


    if html_matches:

        save_debug(
            "html_matches.txt",
            "\n".join(html_matches)
        )


        all_matches.extend(
            html_matches
        )


    # -----------------------------------------------------
    # Обобщен файл
    # -----------------------------------------------------

    if all_matches:

        save_debug(
            "ALL_JAVASCRIPT_MATCHES.txt",
            "\n".join(all_matches)
        )


    print()
    print(
        "================================================"
    )

    print(
        "🔬 JAVASCRIPT SCANNER ГОТОВ"
    )

    print(
        "📁 Резултатите са в:",
        DEBUG_DIR
    )

    print(
        "================================================"
    )

    print()


# =========================================================
# EXTRACT PRODUCT ID
# =========================================================

def extract_product_id(html):

    ids = re.findall(
        r'data-product-id=["\'](\d+)["\']',
        html,
        re.I
    )


    if not ids:

        ids = re.findall(
            r'product.?id.?[:="\']+(\d+)',
            html,
            re.I
        )


    ids = list(
        dict.fromkeys(ids)
    )


    print(
        "ID кандидати:",
        ids
    )


    if ids:

        return ids[0]


    return None


# =========================================================
# MAIN
# =========================================================

def main():

    # -----------------------------------------------------
    # RESET DEBUG
    # -----------------------------------------------------

    init_debug_folder()


    # -----------------------------------------------------
    # INIT CSV
    # -----------------------------------------------------

    init_csv()


    # -----------------------------------------------------
    # READ SKU
    # -----------------------------------------------------

    skus = read_skus()


    print(
        "Общо SKU:",
        len(skus)
    )


    scanner_done = False


    for sku in skus:

        print(
            "================"
        )


        print(
            "➡️ SKU:",
            sku
        )


        # -------------------------------------------------
        # SEARCH
        # -------------------------------------------------

        html = search_filstar(
            sku
        )


        if not html:

            print(
                "❌ Няма резултат"
            )


            save_not_found(
                sku
            )


            continue


        # -------------------------------------------------
        # Пускаме JS scanner само веднъж
        # -------------------------------------------------

        if not scanner_done:

            scan_javascript(
                html
            )

            scanner_done = True


        # -------------------------------------------------
        # PRODUCT ID
        # -------------------------------------------------

        product_id = extract_product_id(
            html
        )


        if product_id:

            print(
                "✅ Product ID:",
                product_id
            )

        else:

            print(
                "⚠️ Product ID не е намерено"
            )


        # -------------------------------------------------
        # ВАЖНО:
        #
        # НЕ извикваме:
        #
        # /get-serialize-product/
        #
        # защото GitHub Actions получава HTTP 403.
        #
        # На този етап само събираме JS информацията,
        # за да открием реалния публичен endpoint.
        # -------------------------------------------------

        print(
            "⏭️ Serialize endpoint пропуснат."
        )


        # -------------------------------------------------
        # Временно записваме SKU като not found.
        #
        # След като открием endpoint-а,
        # тук ще поставим реалното извличане.
        # -------------------------------------------------

        save_not_found(
            sku
        )


        time.sleep(
            WAIT
        )


    print(
        "💾 Записани резултати:",
        RESULT_CSV
    )


    print(
        "💾 Not found:",
        NOT_FOUND_CSV
    )


    print(
        "📁 Debug:",
        DEBUG_DIR
    )


    print(
        "✅ Диагностиката приключи"
    )


if __name__ == "__main__":

    main()
