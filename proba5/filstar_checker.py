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
            "SEARCH ERROR:",
            e
        )

        return None


    debug(
        f"search_{sku}.html",
        html
    )

    return html


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


def get_product_data(product_id):

    url = f"{BASE_URL}/get-serialize-product/{product_id}"

    print(
        "📦 PRODUCT:",
        url
    )

    product_headers = {

        "Accept":
        "application/json, text/plain, */*",

        "Accept-Language":
        "bg-BG,bg;q=0.9,en;q=0.8",

        "Referer":
        f"{BASE_URL}/",

        "X-Requested-With":
        "XMLHttpRequest",

        "Sec-Fetch-Dest":
        "empty",

        "Sec-Fetch-Mode":
        "cors",

        "Sec-Fetch-Site":
        "same-origin"

    }

    try:

        r = session.get(
            url,
            headers=product_headers,
            timeout=30
        )

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

            return r.json()

        except Exception as e:

            print(
                "❌ JSON ERROR:",
                e
            )

            return None

    except Exception as e:

        print(
            "PRODUCT ERROR:",
            e
        )

        return None


def extract_total_quantity(product_data, sku):

    variants = product_data.get(
        "variants",
        []
    )

    if not variants:

        print(
            "⚠️ Няма variants"
        )

        return None


    total_quantity = 0

    found_sku = False


    for variant in variants:

        variant_sku = str(
            variant.get(
                "sku",
                ""
            )
        )

        if variant_sku == str(sku):

            found_sku = True

            quantity = variant.get(
                "quantity"
            )

            if quantity is not None:

                try:

                    total_quantity += int(
                        quantity
                    )

                except (ValueError, TypeError):

                    pass


    if found_sku:

        return total_quantity


    # Ако SKU не е намерено директно,
    # използваме всички варианти на продукта.

    total_quantity = 0

    for variant in variants:

        quantity = variant.get(
            "quantity"
        )

        if quantity is not None:

            try:

                total_quantity += int(
                    quantity
                )

            except (ValueError, TypeError):

                pass


    return total_quantity


def extract_price_from_product(product_data, sku):

    variants = product_data.get(
        "variants",
        []
    )

    for variant in variants:

        if str(
            variant.get("sku", "")
        ) == str(sku):

            price = variant.get(
                "price"
            )

            if price is not None:

                return str(
                    price
                )

    price = product_data.get(
        "price"
    )

    if price is not None:

        return str(
            price
        )

    return None


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

            time.sleep(WAIT)

            continue


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

            time.sleep(WAIT)

            continue


        quantity = extract_total_quantity(
            product_data,
            sku
        )


        if quantity is not None:

            print(
                "📦 Общо количество:",
                quantity
            )

        else:

            print(
                "⚠️ Количеството не е намерено"
            )


        price = extract_price_from_product(
            product_data,
            sku
        )


        if price:

            print(
                "💶 Цена EUR:",
                price
            )

        else:

            print(
                "⚠️ Няма цена"
            )


        if price:

            if quantity is not None:

                if quantity > 0:

                    availability = "Наличен"

                else:

                    availability = "Неналичен"

            else:

                availability = "Неизвестна"


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


        time.sleep(WAIT)


    print(
        "✅ Готово"
    )


if __name__ == "__main__":

    main()
