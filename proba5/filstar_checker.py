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

        with open(
            os.path.join(
                DEBUG_DIR,
                name
            ),
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


            if line.upper() == "SKU":

                continue


            # Всичко между ## и ## се игнорира
            if line == "##":

                block = not block

                continue


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
            "SEARCH ERROR:",
            e
        )

        return None


    debug(
        f"search_{sku}.html",
        html
    )


    return html


# =========================================================
# EXTRACT PRODUCT ID
# =========================================================

def extract_product_id(html):

    ids = re.findall(
        r'/get-serialize-product/(\d+)',
        html
    )


    if not ids:

        ids = re.findall(
            r'product.?id.?[:="\']+(\d+)',
            html,
            re.I
        )


    ids = list(
        dict.fromkeys(
            ids
        )
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

        # 43.30 €
        r'/\s*(\d+\.\d+)\s*€',

        # 43,30 €
        r'/\s*(\d+,\d+)\s*€',

        # fallback: директно число пред €
        r'(\d+\.\d+)\s*€',

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

def extract_availability(
    html,
    product_id
):

    """
    Намира конкретния product-item-wapper блок
    по data-product-id.

    ВАЖНО:
    Не използваме фиксиран брой символи след Product ID,
    защото така може да попаднем в следващ продукт.

    Всеки product-item-wapper се разглежда отделно.
    """

    product_blocks = list(
        re.finditer(
            r'<div[^>]*class=["\'][^"\']*product-item-wapper[^"\']*["\'][^>]*>',
            html,
            re.I
        )
    )


    # Ако няма намерени продуктови блокове
    if not product_blocks:

        print(
            "⚠️ Product блокове не са намерени"
        )

        return "Неизвестна"


    # Обхождаме всеки продуктов блок
    for i, match in enumerate(
        product_blocks
    ):

        start = match.start()


        # Край на текущия блок =
        # начало на следващия блок
        if i + 1 < len(
            product_blocks
        ):

            end = product_blocks[
                i + 1
            ].start()


            block = html[
                start:end
            ]


        else:

            block = html[
                start:
            ]


        # -------------------------------------------------
        # Проверяваме дали това е нашият Product ID
        # -------------------------------------------------

        id_match = re.search(
            r'data-product-id=["\']'
            + re.escape(
                str(product_id)
            )
            + r'["\']',
            block,
            re.I
        )


        if not id_match:

            continue


        # -------------------------------------------------
        # Намерихме точния продукт
        # -------------------------------------------------

        block_lower = block.lower()


        # -------------------------------------------------
        # НЕНАЛИЧЕН
        # -------------------------------------------------

        if re.search(
            r'\bout-of-stock\b',
            block_lower,
            re.I
        ):

            return "Неналичен"


        if re.search(
            r'\bproduct-not-available\b',
            block_lower,
            re.I
        ):

            return "Неналичен"


        if re.search(
            r'\btag-not-available\b',
            block_lower,
            re.I
        ):

            return "Неналичен"


        # -------------------------------------------------
        # Няма маркер за неналичност
        # -------------------------------------------------

        return "Наличен"


    print(
        "⚠️ Product блокът не е намерен за ID:",
        product_id
    )


    return "Неизвестна"


# =========================================================
# EXTRACT QUANTITY
# =========================================================

def extract_quantity(
    html,
    sku
):

    patterns = [

        # "quantity":3,"sku":"950594"
        r'"quantity"\s*:\s*(\d+)'
        r'.*?'
        r'"sku"\s*:\s*"'
        + re.escape(sku)
        + r'"',

        # "sku":"950594"... "quantity":3
        r'"sku"\s*:\s*"'
        + re.escape(sku)
        + r'"'
        r'.*?'
        r'"quantity"\s*:\s*(\d+)'

    ]


    for pattern in patterns:

        m = re.search(
            pattern,
            html,
            re.I | re.S
        )


        if m:

            return int(
                m.group(1)
            )


    return None


# =========================================================
# MAIN
# =========================================================

def main():

    # -----------------------------------------------------
    # CSV initialization
    # -----------------------------------------------------

    init_csv()


    # -----------------------------------------------------
    # Read SKU list
    # -----------------------------------------------------

    skus = read_skus()


    print(
        "Общо SKU:",
        len(skus)
    )


    # -----------------------------------------------------
    # Process each SKU
    # -----------------------------------------------------

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
                "❌ Няма Product ID"
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
            html,
            product_id
        )


        if availability == "Наличен":

            print(
                "✅ Наличност: Наличен"
            )


        elif availability == "Неналичен":

            print(
                "✅ Наличност: Неналичен"
            )


        else:

            print(
                "⚠️ Наличността не е намерена"
            )


        # -------------------------------------------------
        # QUANTITY
        # -------------------------------------------------

        quantity = extract_quantity(
            html,
            sku
        )


        if quantity is not None:

            print(
                "✅ Quantity:",
                quantity
            )


        else:

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
                    availability,
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


    # -----------------------------------------------------
    # DONE
    # -----------------------------------------------------

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
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    main()
