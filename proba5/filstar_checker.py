#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import re
import time
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
    "AppleWebKit/537.36 Chrome/128 Safari/537.36",

    "Accept":
    "application/json, text/plain, */*",

    "Accept-Language":
    "bg-BG,bg;q=0.9,en;q=0.8",

    "X-Requested-With":
    "XMLHttpRequest"

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

        r.raise_for_status()

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

    ids = list(dict.fromkeys(ids))

    print(
        "ID кандидати:",
        ids
    )

    if ids:

        return ids[0]

    return None


def get_product_data(product_id):

    url = f"{BASE_URL}/get-serialize-product/{product_id}"

    print(
        "🌐 DATA:",
        url
    )

    try:

        r = session.get(
            url,
            timeout=30,
            headers={
                "Accept": "*/*",
                "X-Requested-With": "XMLHttpRequest"
            }
        )

        r.raise_for_status()

        data = r.json()

        debug(
            f"product_data_{product_id}.json",
            r.text
        )

        return data

    except Exception as e:

        print(
            "DATA ERROR:",
            e
        )

        return None


def extract_variant(data, sku):

    if not data:

        return None

    variants = data.get(
        "variants",
        []
    )

    sku = str(sku).strip()

    for variant in variants:

        variant_sku = str(
            variant.get(
                "sku",
                ""
            )
        ).strip()

        if variant_sku == sku:

            return variant

    default_variant = data.get(
        "defaultVariant"
    )

    if default_variant:

        default_sku = str(
            default_variant.get(
                "sku",
                ""
            )
        ).strip()

        if default_sku == sku:

            return default_variant

    return None


def extract_price(variant):

    if not variant:

        return None

    price = variant.get(
        "discountedPrice"
    )

    if price is None:

        price = variant.get(
            "price"
        )

    if price is None:

        return None

    try:

        return f"{float(price):.2f}"

    except Exception:

        return str(price)


def extract_quantity(variant):

    if not variant:

        return None

    quantity = variant.get(
        "quantity"
    )

    if quantity is None:

        return None

    try:

        return int(quantity)

    except Exception:

        return quantity


def main():

    init_csv()

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

            continue


        print(
            "✅ Product ID:",
            product_id
        )


        data = get_product_data(
            product_id
        )


        if not data:

            print(
                "❌ Няма product data"
            )

            save_not_found(
                sku
            )

            time.sleep(WAIT)

            continue


        variant = extract_variant(
            data,
            sku
        )


        if not variant:

            print(
                "❌ SKU не е намерено във variants:",
                sku
            )

            save_not_found(
                sku
            )

            time.sleep(WAIT)

            continue


        quantity = extract_quantity(
            variant
        )

        price = extract_price(
            variant
        )


        if quantity is None:

            print(
                "⚠️ Quantity не е намерено"
            )

            availability = "Неизвестна"

            quantity_output = "-"

        else:

            quantity_output = quantity

            if quantity > 0:

                availability = "Наличен"

            else:

                availability = "Изчерпан"


            print(
                "📦 Наличност:",
                availability
            )

            print(
                "📦 Бройки:",
                quantity
            )


        if price:

            print(
                "✅ Цена:",
                price
            )

        else:

            print(
                "❌ Няма цена"
            )


        if price:

            save_result(
                [
                    sku,
                    availability,
                    quantity_output,
                    price
                ]
            )

        else:

            save_result(
                [
                    sku,
                    availability,
                    quantity_output,
                    "-"
                ]
            )


        time.sleep(WAIT)


    print(
        "✅ Готово"
    )


if __name__ == "__main__":

    main()
