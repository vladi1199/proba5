#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import re
import time
import requests


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

os.makedirs(
    DEBUG_DIR,
    exist_ok=True
)


BASE_URL = "https://filstar.com"

WAIT = 2


HEADERS = {

    "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/128 Safari/537.36",

    "Accept":
        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",

    "Accept-Language":
        "bg-BG,bg;q=0.9,en;q=0.8"

}


session = requests.Session()

session.headers.update(
    HEADERS
)


# =========================================================
# DEBUG
# =========================================================

def debug(name, data):

    try:

        path = os.path.join(
            DEBUG_DIR,
            name
        )

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(data)

        print(
            "🐞 Debug:",
            name
        )

    except Exception:
        pass


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

            # Пропускаме header-а
            if line.upper() == "SKU":
                continue

            # ## започва/приключва блок,
            # който НЕ трябва да се обработва
            if line == "##":

                block = not block

                continue

            # Всичко между ## и ## се пропуска
            if block:
                continue

            result.append(
                line
            )

    return result


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

    except Exception as e:

        print(
            "❌ SEARCH ERROR:",
            e
        )

        return None


    debug(
        f"search_{sku}.html",
        html
    )

    if r.status_code != 200:

        print(
            "❌ Search HTTP:",
            r.status_code
        )

        return None


    return html


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
            r'/get-serialize-product/(\d+)',
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
# EXTRACT PRICE
# =========================================================

def extract_price(html):

    patterns = [

        # Например:
        # 76.00 лв. / 38.86 €
        r'/\s*(\d+\.\d+)\s*€',

        # Например:
        # 76,00 лв. / 38,86 €
        r'/\s*(\d+,\d+)\s*€',

        # Fallback:
        # 38.86 €
        r'(\d+\.\d+)\s*€',

        # Fallback:
        # 38,86 €
        r'(\d+,\d+)\s*€'

    ]

    for pattern in patterns:

        m = re.search(
            pattern,
            html,
            re.I
        )

        if m:

            price = m.group(1)

            return price.replace(
                ",",
                "."
            )

    return None


# =========================================================
# EXTRACT AVAILABILITY
# =========================================================

def extract_availability(html):

    html_lower = html.lower()


    # -----------------------------------------------------
    # 1. Основният клас на Filstar за неналичен продукт
    #
    # class="product-item-wapper product-not-available out-of-stock"
    # -----------------------------------------------------

    if re.search(
        r'class=["\'][^"\']*\bout-of-stock\b[^"\']*["\']',
        html_lower,
        re.I
    ):

        return "Неналичен"


    # -----------------------------------------------------
    # 2. product-not-available
    # -----------------------------------------------------

    if re.search(
        r'class=["\'][^"\']*\bproduct-not-available\b[^"\']*["\']',
        html_lower,
        re.I
    ):

        return "Неналичен"


    # -----------------------------------------------------
    # 3. tag-not-available
    #
    # Например:
    #
    # <div class="tag tag-not-available">
    #     Очакваме
    # </div>
    # -----------------------------------------------------

    if re.search(
        r'class=["\'][^"\']*\btag-not-available\b[^"\']*["\']',
        html_lower,
        re.I
    ):

        return "Неналичен"


    # -----------------------------------------------------
    # 4. Ако има текст "Очакваме"
    # -----------------------------------------------------

    if re.search(
        r'>\s*Очакваме\s*<',
        html,
        re.I
    ):

        return "Неналичен"


    # -----------------------------------------------------
    # Ако няма нито един от горните маркери,
    # приемаме продукта за наличен.
    # -----------------------------------------------------

    return "Наличен"


# =========================================================
# MAIN
# =========================================================

def main():

    init_csv()


    skus = read_skus()


    print(
        "Общо SKU:",
        len(skus)
    )


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

            time.sleep(
                WAIT
            )

            continue


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
                "❌ Няма Product ID за SKU:",
                sku
            )

            save_not_found(
                sku
            )

            time.sleep(
                WAIT
            )

            continue


        # -------------------------------------------------
        # AVAILABILITY
        # -------------------------------------------------

        availability = extract_availability(
            html
        )


        if availability:

            print(
                "✅ Наличност:",
                availability
            )

        else:

            print(
                "⚠️ Наличността не е намерена"
            )


        # -------------------------------------------------
        # QUANTITY
        #
        # НЕ правим product endpoint заявка.
        # В search HTML няма надеждна складова бройка.
        # -------------------------------------------------

        quantity = None

        print(
            "⚠️ Quantity не е намерено"
        )


        # -------------------------------------------------
        # PRICE
        # -------------------------------------------------

        price = extract_price(
            html
        )


        if price:

            print(
                "✅ Цена EUR:",
                price
            )

        else:

            print(
                "❌ Няма EUR цена"
            )


        # -------------------------------------------------
        # SAVE
        # -------------------------------------------------

        if price:

            save_result(
                [
                    sku,

                    availability
                    if availability
                    else "Неизвестна",

                    quantity
                    if quantity is not None
                    else "-",

                    price
                ]
            )

        else:

            save_not_found(
                sku
            )


        # -------------------------------------------------
        # WAIT
        # -------------------------------------------------

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
        "✅ Готово"
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    main()
