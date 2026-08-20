#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import re
import time
import json
import requests


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SKU_CSV = os.path.join(BASE_DIR, "sku_list_filstar.csv")

RESULT_CSV = os.path.join(BASE_DIR, "results_filstar.csv")
NOT_FOUND_CSV = os.path.join(BASE_DIR, "not_found_filstar.csv")

DEBUG_DIR = os.path.join(BASE_DIR, "debug_html")

os.makedirs(DEBUG_DIR, exist_ok=True)


BASE_URL = "https://filstar.com"

WAIT = 2


HEADERS = {
    "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36",

    "Accept":
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8",

    "Accept-Language":
        "bg-BG,bg;q=0.9,en;q=0.8",

    "Connection":
        "keep-alive"
}


session = requests.Session()
session.headers.update(HEADERS)


def debug(name, data):

    try:

        with open(
            os.path.join(DEBUG_DIR, name),
            "w",
            encoding="utf-8"
        ) as f:

            f.write(data)

        print("🐞 Debug:", name)

    except Exception:
        pass


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


def save_result(row):

    with open(
        RESULT_CSV,
        "a",
        newline="",
        encoding="utf-8"
    ) as f:

        csv.writer(f).writerow(row)


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


# ============================================================
# SEARCH
# ============================================================

def search_filstar(sku):

    url = f"{BASE_URL}/api/search?term={sku}"

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

    return html


# ============================================================
# PRODUCT ID
# ============================================================

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


# ============================================================
# PRODUCT DATA
# ============================================================

def get_product_data(product_id):

    url = (
        f"{BASE_URL}/get-serialize-product/"
        f"{product_id}"
    )

    print(
        "📦 PRODUCT:",
        url
    )

    headers = {
        "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36",

        "Accept":
            "application/json, text/plain, */*",

        "Accept-Language":
            "bg-BG,bg;q=0.9,en;q=0.8",

        "Referer":
            f"{BASE_URL}/",

        "X-Requested-With":
            "XMLHttpRequest",

        "Connection":
            "keep-alive"
    }

    try:

        r = session.get(
            url,
            headers=headers,
            timeout=30
        )

    except Exception as e:

        print(
            "❌ Product ERROR:",
            e
        )

        return None


    print(
        "📡 Product HTTP:",
        r.status_code
    )

    if r.status_code != 200:

        print(
            "❌ Product HTTP:",
            r.status_code
        )

        debug(
            f"product_{product_id}_error.html",
            r.text
        )

        return None


    debug(
        f"product_{product_id}.json",
        r.text
    )


    try:

        data = r.json()

    except Exception as e:

        print(
            "❌ JSON ERROR:",
            e
        )

        debug(
            f"product_{product_id}_invalid.json",
            r.text
        )

        return None


    return data


# ============================================================
# FIND VARIANT
# ============================================================

def find_variant(product_data, sku):

    if not isinstance(
        product_data,
        dict
    ):

        return None


    variants = product_data.get(
        "variants"
    )


    if not isinstance(
        variants,
        list
    ):

        print(
            "❌ Product няма variants"
        )

        return None


    print(
        "🔍 Брой variants:",
        len(variants)
    )


    for variant in variants:

        if not isinstance(
            variant,
            dict
        ):
            continue


        variant_sku = str(
            variant.get(
                "sku",
                ""
            )
        ).strip()


        if variant_sku == str(sku).strip():

            print(
                "✅ Variant намерен:",
                variant.get("id"),
                "SKU:",
                variant_sku
            )

            return variant


    return None


# ============================================================
# TOTAL QUANTITY
# ============================================================

def extract_total_quantity(variant):

    if not isinstance(
        variant,
        dict
    ):

        return None


    stores = variant.get(
        "stores"
    )


    # Ако variant директно няма stores,
    # проверяваме дали има quantity.
    if not isinstance(
        stores,
        list
    ):

        quantity = variant.get(
            "quantity"
        )

        if quantity is not None:

            try:
                return int(quantity)

            except Exception:
                return None

        return None


    total = 0

    found = False


    for store in stores:

        if not isinstance(
            store,
            dict
        ):
            continue


        quantity = store.get(
            "quantity"
        )


        if quantity is None:
            continue


        try:

            total += int(
                quantity
            )

            found = True

        except Exception:

            pass


    if found:

        return total


    # fallback
    quantity = variant.get(
        "quantity"
    )


    if quantity is not None:

        try:
            return int(quantity)

        except Exception:
            return None


    return None


# ============================================================
# PRICE
# ============================================================

def extract_variant_price(variant):

    if not isinstance(
        variant,
        dict
    ):

        return None


    # Първо discountedPrice
    price = variant.get(
        "discountedPrice"
    )


    if price is None:

        price = variant.get(
            "price"
        )


    if price is None:

        price = variant.get(
            "discountedRetailPrice"
        )


    if price is None:

        return None


    try:

        price = float(
            price
        )

    except Exception:

        return None


    # Заобикаляме проблемите с
    # floating point числата
    return f"{price:.2f}"


# ============================================================
# FALLBACK PRICE FROM SEARCH HTML
# ============================================================

def extract_price_from_search(html):

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

            return price.replace(
                ",",
                "."
            )


    return None


# ============================================================
# MAIN
# ============================================================

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


        # ----------------------------------------------------
        # 1. SEARCH
        # ----------------------------------------------------

        html = search_filstar(
            sku
        )


        if not html:

            print(
                "❌ Няма search резултат"
            )

            save_not_found(
                sku
            )

            time.sleep(
                WAIT
            )

            continue


        # ----------------------------------------------------
        # 2. PRODUCT ID
        # ----------------------------------------------------

        product_id = extract_product_id(
            html
        )


        if not product_id:

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


        print(
            "✅ Product ID:",
            product_id
        )


        # ----------------------------------------------------
        # 3. PRODUCT JSON
        # ----------------------------------------------------

        product_data = get_product_data(
            product_id
        )


        if not product_data:

            print(
                "❌ Няма product data"
            )

            save_not_found(
                sku
            )

            time.sleep(
                WAIT
            )

            continue


        print(
            "✅ Product JSON получен"
        )


        # ----------------------------------------------------
        # 4. VARIANT
        # ----------------------------------------------------

        variant = find_variant(
            product_data,
            sku
        )


        if not variant:

            print(
                "❌ Няма variant за SKU:",
                sku
            )

            save_not_found(
                sku
            )

            time.sleep(
                WAIT
            )

            continue


        # ----------------------------------------------------
        # 5. QUANTITY
        # ----------------------------------------------------

        quantity = extract_total_quantity(
            variant
        )


        if quantity is not None:

            print(
                "📦 Общо количество:",
                quantity
            )

        else:

            print(
                "⚠️ Quantity не е намерено"
            )


        # ----------------------------------------------------
        # 6. PRICE
        # ----------------------------------------------------

        price = extract_variant_price(
            variant
        )


        # Ако няма цена във variant,
        # взимаме цената от search HTML.
        if not price:

            price = extract_price_from_search(
                html
            )


        if price:

            print(
                "💶 Цена EUR:",
                price
            )

        else:

            print(
                "❌ Няма цена"
            )


        # ----------------------------------------------------
        # 7. AVAILABILITY
        # ----------------------------------------------------

        if quantity is not None:

            if quantity > 0:

                availability = "Наличен"

            else:

                availability = "Неналичен"

        else:

            availability = "Неизвестна"


        print(
            "📊 Наличност:",
            availability
        )


        # ----------------------------------------------------
        # 8. SAVE
        # ----------------------------------------------------

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
        "✅ Готово"
    )


if __name__ == "__main__":

    main()
