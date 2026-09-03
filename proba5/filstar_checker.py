#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import re
import time
import requests
import shutil


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

    # Изтриваме цялата стара debug папка
    if os.path.exists(DEBUG_DIR):

        print(
            "🗑️ Изтривам старата debug папка:",
            DEBUG_DIR
        )

        shutil.rmtree(DEBUG_DIR)

    # Създаваме чиста debug папка
    os.makedirs(
        DEBUG_DIR,
        exist_ok=True
    )

    print(
        "📁 Създадена е нова debug папка:",
        DEBUG_DIR
    )


# =========================================================
# SAVE DEBUG HTML
# =========================================================

def save_debug_html(filename, html):

    if not html:
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

            f.write(html)

        print(
            "💾 Debug HTML:",
            filepath
        )

    except Exception as e:

        print(
            "⚠️ Грешка при запис на debug HTML:",
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

        # -------------------------------------------------
        # SAVE SEARCH HTML FOR DEBUG
        # -------------------------------------------------

        save_debug_html(
            f"search_{sku}.html",
            html
        )

    except Exception as e:

        print(
            "SEARCH ERROR:",
            e
        )

        return None


    return html


# =========================================================
# EXTRACT PRODUCT URL
# =========================================================

def extract_product_url(html):

    for match in re.finditer(
        r'<a\b[^>]*>',
        html,
        re.I
    ):

        tag = match.group(0)

        if "product-name" not in tag:
            continue

        href_match = re.search(
            r'href=["\']([^"\']+)["\']',
            tag,
            re.I
        )

        if href_match:

            href = href_match.group(1)

            if href.startswith("/"):

                href = BASE_URL + href

            return href

    return None


# =========================================================
# FETCH PRODUCT PAGE
# =========================================================

def fetch_product_page(url):

    try:

        r = session.get(
            url,
            timeout=30
        )

        print(
            "🔎 Product page HTTP:",
            r.status_code
        )

        return r.text

    except Exception as e:

        print(
            "PRODUCT PAGE ERROR:",
            e
        )

        return None


# =========================================================
# EXTRACT PRICE FOR EXACT SKU
# =========================================================

def extract_variant_price(html, sku):

    """
    Продукти с няколко варианта (цвят/размер) показват само
    ЕДНА обща цена на страницата за търсене — тази на "показания"
    вариант.

    За точната цена по конкретен SKU трябва да се прочете
    таблицата за бърза поръчка (fast-order-table) на
    продуктовата страница, ред по ред.
    """

    table_match = re.search(
        r'id=["\']fast-order-table["\'].*?<tbody[^>]*>(.*?)</tbody>',
        html,
        re.I | re.S
    )

    if not table_match:

        return None

    tbody_html = table_match.group(1)

    rows = re.findall(
        r'<tr\b[^>]*>(.*?)</tr>',
        tbody_html,
        re.I | re.S
    )

    for row in rows:

        code_match = re.search(
            r'class=["\'][^"\']*td-sky[^"\']*["\'][^>]*>(.*?)</td>',
            row,
            re.I | re.S
        )

        row_matches_sku = False

        if code_match:

            code_text = re.sub(
                r'<[^>]+>',
                '',
                code_match.group(1)
            )

            code_digits = re.sub(
                r'\D+',
                '',
                code_text
            )

            if code_digits == str(sku):

                row_matches_sku = True

        if not row_matches_sku:

            # fallback: SKU споменат някъде в реда като текст
            if re.search(
                rf'\b{re.escape(str(sku))}\b',
                row
            ):

                row_matches_sku = True

        if not row_matches_sku:

            continue

        # -------------------------------------------------
        # Намерихме реда — вадим цената именно от него
        # -------------------------------------------------

        price = None

        strike_match = re.search(
            r'<strike[^>]*>(.*?)</strike>',
            row,
            re.I | re.S
        )

        if strike_match:

            m = re.search(
                r'(\d+[.,]\d+)\s*€',
                strike_match.group(1)
            )

            if m:

                price = m.group(1).replace(",", ".")

        if price is None:

            m2 = re.search(
                r'(\d+[.,]\d+)\s*€',
                row
            )

            if m2:

                price = m2.group(1).replace(",", ".")

        return price

    return None


# =========================================================
# EXTRACT PRICE
# =========================================================

def extract_price(html):

    patterns = [

        r'/\s*(\d+\.\d+)\s*€',
        r'/\s*(\d+,\d+)\s*€',
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

            return price.replace(",", ".")

    return None


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
# EXTRACT AVAILABILITY
# =========================================================

def extract_availability(
    html,
    product_id
):

    pattern = (
        r'<div\b[^>]*'
        r'class=["\'][^"\']*product-item-wapper[^"\']*["\']'
        r'[^>]*>'
    )

    matches = re.finditer(
        pattern,
        html,
        re.I
    )

    for match in matches:

        opening_tag = match.group(0)

        id_match = re.search(
            r'data-product-id=["\']'
            + re.escape(str(product_id))
            + r'["\']',
            opening_tag,
            re.I
        )

        if not id_match:

            continue

        classes_match = re.search(
            r'class=["\']([^"\']*)["\']',
            opening_tag,
            re.I
        )

        if not classes_match:

            return "Неизвестна"

        classes = classes_match.group(1).lower()

        if "out-of-stock" in classes:

            return "Неналичен"

        if "product-not-available" in classes:

            return "Неналичен"

        return "Наличен"

    return "Неизвестна"


# =========================================================
# EXTRACT QUANTITY
# =========================================================

def extract_quantity(
    html,
    sku
):

    patterns = [

        r'"quantity"\s*:\s*(\d+)'
        r'.*?'
        r'"sku"\s*:\s*"'
        + re.escape(sku)
        + r'"',

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

            return int(m.group(1))

    return None


# =========================================================
# MAIN
# =========================================================

def main():

    # -------------------------------------------------
    # RESET DEBUG FOLDER
    # -------------------------------------------------

    init_debug_folder()

    # -------------------------------------------------
    # INIT CSV
    # -------------------------------------------------

    init_csv()

    # -------------------------------------------------
    # READ SKU
    # -------------------------------------------------

    skus = read_skus()

    print(
        "Общо SKU:",
        len(skus)
    )

    for sku in skus:

        print("================")

        print(
            "➡️ SKU:",
            sku
        )

        # -------------------------------------------------
        # SEARCH
        # -------------------------------------------------

        html = search_filstar(sku)

        if not html:

            print(
                "❌ Няма резултат"
            )

            save_not_found(sku)

            continue

        # -------------------------------------------------
        # PRODUCT ID
        # -------------------------------------------------

        product_id = extract_product_id(
            html
        )

        if not product_id:

            print(
                "❌ Няма Product ID"
            )

            save_not_found(sku)

            time.sleep(WAIT)

            continue

        print(
            "✅ Product ID:",
            product_id
        )

        # -------------------------------------------------
        # AVAILABILITY
        # -------------------------------------------------

        availability = extract_availability(
            html,
            product_id
        )

        print(
            "✅ Наличност:",
            availability
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

        price = None

        product_url = extract_product_url(
            html
        )

        if product_url:

            print(
                "🔗 Продуктова страница:",
                product_url
            )

            product_html = fetch_product_page(
                product_url
            )

            # -------------------------------------------------
            # SAVE PRODUCT HTML FOR DEBUG
            # -------------------------------------------------

            if product_html:

                save_debug_html(
                    f"product_{sku}.html",
                    product_html
                )

                price = extract_variant_price(
                    product_html,
                    sku
                )

                if price:

                    print(
                        "✅ Точна цена по SKU:",
                        price
                    )

                else:

                    print(
                        "⚠️ SKU не е намерен в fast-order-table, "
                        "ползвам общата цена като fallback"
                    )

        else:

            print(
                "⚠️ Няма линк към продуктова страница"
            )

        # -------------------------------------------------
        # FALLBACK PRICE
        # -------------------------------------------------

        if not price:

            price = extract_price(
                html
            )

            if price:

                print(
                    "⚠️ Fallback обща цена:",
                    price
                )

        if price:

            print(
                "✅ Крайна цена:",
                price
            )

        else:

            print(
                "❌ Няма намерена цена"
            )

        # -------------------------------------------------
        # SAVE
        # -------------------------------------------------

        if price:

            save_result(
                [
                    sku,
                    availability,
                    quantity if quantity is not None else "-",
                    price
                ]
            )

        else:

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
        "✅ Готово"
    )


if __name__ == "__main__":

    main()
