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
    "AppleWebKit/537.36 Chrome/128 Safari/537.36",

    "Accept":
    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",

    "Accept-Language":
    "bg-BG,bg;q=0.9,en;q=0.8"

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
            "❌ SEARCH ERROR:",
            e
        )

        return None


    debug(
        f"search_{sku}.html",
        html
    )

    if r.status_code != 200:

        return None

    return html


def extract_price_from_variant(variant):

    price_fields = [
        "discountedPrice",
        "discountedRetailPrice",
        "price"
    ]

    for field in price_fields:

        value = variant.get(field)

        if value is not None:

            try:

                return f"{float(value):.2f}"

            except Exception:
                pass

    return None


def calculate_total_quantity(variant):

    """
    Връща общото количество от всички складове.

    Например:

    stores:
        Пловдив = 1
        София = 0

    Резултат:
        1
    """

    stores = variant.get("stores")

    if isinstance(stores, list):

        total = 0

        found = False

        for store in stores:

            if not isinstance(store, dict):
                continue

            quantity = store.get("quantity")

            if quantity is None:
                continue

            try:

                total += int(quantity)

                found = True

            except (ValueError, TypeError):

                continue

        if found:
            return total


    # fallback
    quantity = variant.get("quantity")

    if quantity is not None:

        try:
            return int(quantity)

        except (ValueError, TypeError):
            pass


    return None


def find_variant_by_sku(data, sku):

    """
    Търси рекурсивно variant със съответния SKU
    в JSON структурата на search резултата.
    """

    if isinstance(data, dict):

        # Проверяваме директно този обект
        current_sku = data.get("sku")

        if current_sku is not None:

            if str(current_sku).strip() == str(sku).strip():

                # Проверяваме дали това действително е variant
                if (
                    "price" in data
                    or "quantity" in data
                    or "stores" in data
                ):

                    return data


        # Продължаваме рекурсивно
        for value in data.values():

            result = find_variant_by_sku(
                value,
                sku
            )

            if result is not None:
                return result


    elif isinstance(data, list):

        for item in data:

            result = find_variant_by_sku(
                item,
                sku
            )

            if result is not None:
                return result


    return None


def extract_json_objects(html):

    """
    Търси JSON обекти, които са вградени
    в HTML / JavaScript кода.

    Не разчитаме на конкретно име
    на JavaScript variable.
    """

    objects = []

    decoder = json.JSONDecoder()

    length = len(html)

    position = 0

    while position < length:

        start = html.find("{", position)

        if start == -1:
            break

        try:

            obj, end = decoder.raw_decode(
                html[start:]
            )

            objects.append(obj)

            position = start + end

        except (json.JSONDecodeError, ValueError):

            position = start + 1

    return objects


def extract_variant_from_search(html, sku):

    """
    Опитва няколко начина да намери
    variant-а за конкретния SKU.
    """

    # -------------------------------------------------
    # 1. Търсим JSON обекти
    # -------------------------------------------------

    objects = extract_json_objects(html)

    print(
        "🔍 JSON обекти:",
        len(objects)
    )

    for obj in objects:

        variant = find_variant_by_sku(
            obj,
            sku
        )

        if variant is not None:

            return variant


    # -------------------------------------------------
    # 2. Fallback - директно търсене в HTML
    # -------------------------------------------------

    escaped_sku = re.escape(str(sku))

    pattern = (
        r'"sku"\s*:\s*"'
        + escaped_sku
        + r'"'
    )

    match = re.search(
        pattern,
        html,
        re.I
    )

    if match:

        print(
            "⚠️ SKU намерено директно в HTML"
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


        # -------------------------------------------------
        # SEARCH
        # -------------------------------------------------

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

            time.sleep(WAIT)

            continue


        # -------------------------------------------------
        # VARIANT
        # -------------------------------------------------

        variant = extract_variant_from_search(
            html,
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

            time.sleep(WAIT)

            continue


        print(
            "✅ Variant намерен:",
            variant.get("id")
        )


        print(
            "🏷️ SKU:",
            variant.get("sku")
        )


        # -------------------------------------------------
        # PRICE
        # -------------------------------------------------

        price = extract_price_from_variant(
            variant
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


        # -------------------------------------------------
        # QUANTITY
        # -------------------------------------------------

        quantity = calculate_total_quantity(
            variant
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


        # -------------------------------------------------
        # AVAILABILITY
        # -------------------------------------------------

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


        time.sleep(WAIT)


    print(
        "✅ Готово"
    )


if __name__ == "__main__":

    main()
