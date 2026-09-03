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
# EXTRACT PRODUCT ID
# =========================================================

def extract_product_id(html):

    ids = re.findall(
        r'/get-serialize-product/(\d+)',
        html,
        re.I
    )


    if not ids:

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
# GET SERIALIZED PRODUCT
# =========================================================

def get_serialized_product(product_id):

    url = (
        f"{BASE_URL}/get-serialize-product/{product_id}"
    )


    print(
        "🌐 SERIALIZE:",
        url
    )


    try:

        r = session.get(
            url,
            timeout=30
        )


        print(
            "🔎 Serialize HTTP:",
            r.status_code
        )


        response_text = r.text


        # -------------------------------------------------
        # Записваме пълния response за debug
        # -------------------------------------------------

        save_debug(
            f"serialize_{product_id}.json",
            response_text
        )


        if r.status_code != 200:

            print(
                "❌ Serialize HTTP грешка:",
                r.status_code
            )

            return None


        try:

            data = r.json()

        except Exception:

            try:

                data = json.loads(
                    response_text
                )

            except Exception as e:

                print(
                    "❌ Response-ът не е валиден JSON:",
                    e
                )

                return None


        return data


    except Exception as e:

        print(
            "SERIALIZE ERROR:",
            e
        )

        return None


# =========================================================
# FIND EXACT VARIANT
# =========================================================

def find_variant(
    product_data,
    sku
):

    if not isinstance(
        product_data,
        dict
    ):

        return None


    variants = product_data.get(
        "variants",
        []
    )


    if not isinstance(
        variants,
        list
    ):

        print(
            "⚠️ Няма variants[]"
        )

        return None


    print(
        "🔎 Общо варианти:",
        len(variants)
    )


    target_sku = str(sku).strip()


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


        if variant_sku == target_sku:

            return variant


    return None


# =========================================================
# EXTRACT PRICE FROM VARIANT
# =========================================================

def extract_variant_price_from_data(
    variant
):

    if not variant:
        return None


    # -----------------------------------------------------
    # Първо използваме discountedPrice,
    # както е показано в AddToCart.js
    # -----------------------------------------------------

    discounted_price = variant.get(
        "discountedPrice"
    )


    if discounted_price is not None:

        try:

            return f"{float(discounted_price):.2f}"

        except Exception:
            pass


    # -----------------------------------------------------
    # Ако няма discountedPrice → price
    # -----------------------------------------------------

    price = variant.get(
        "price"
    )


    if price is not None:

        try:

            return f"{float(price):.2f}"

        except Exception:
            pass


    return None


# =========================================================
# EXTRACT QUANTITY FROM VARIANT
# =========================================================

def extract_variant_quantity(
    variant
):

    if not variant:
        return None


    quantity = variant.get(
        "quantity"
    )


    if quantity is not None:

        try:

            return int(
                quantity
            )

        except Exception:
            pass


    # -----------------------------------------------------
    # Fallback: ако quantity липсва,
    # събираме количествата по магазини
    # -----------------------------------------------------

    stores = variant.get(
        "stores",
        []
    )


    if isinstance(
        stores,
        list
    ):

        total = 0

        found = False


        for store in stores:

            if not isinstance(
                store,
                dict
            ):

                continue


            store_quantity = store.get(
                "quantity"
            )


            if store_quantity is None:
                continue


            try:

                total += int(
                    store_quantity
                )

                found = True

            except Exception:
                pass


        if found:

            return total


    return None


# =========================================================
# EXTRACT AVAILABILITY FROM VARIANT
# =========================================================

def extract_variant_availability(
    variant
):

    quantity = extract_variant_quantity(
        variant
    )


    if quantity is not None:

        if quantity > 0:

            return "Наличен"

        return "Неналичен"


    return "Неизвестна"


# =========================================================
# DEBUG VARIANT
# =========================================================

def print_variant_info(
    variant
):

    if not variant:

        return


    print(
        "────────────────────────────"
    )


    print(
        "✅ Variant ID:",
        variant.get("id")
    )


    print(
        "✅ SKU:",
        variant.get("sku")
    )


    print(
        "✅ Barcode:",
        variant.get("barcode")
    )


    print(
        "✅ Price:",
        variant.get("price")
    )


    print(
        "✅ DiscountedPrice:",
        variant.get("discountedPrice")
    )


    print(
        "✅ Quantity:",
        variant.get("quantity")
    )


    stores = variant.get(
        "stores"
    )


    if stores:

        print(
            "🏪 Stores:"
        )


        for store in stores:

            print(
                "   -",
                store.get("name"),
                ":",
                store.get("quantity")
            )


    print(
        "────────────────────────────"
    )


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


        # -------------------------------------------------
        # GET SERIALIZED PRODUCT
        # -------------------------------------------------

        product_data = get_serialized_product(
            product_id
        )


        if not product_data:

            print(
                "❌ Няма Serialized Product данни"
            )


            save_not_found(
                sku
            )


            time.sleep(
                WAIT
            )


            continue


        # -------------------------------------------------
        # FIND EXACT SKU VARIANT
        # -------------------------------------------------

        variant = find_variant(
            product_data,
            sku
        )


        if not variant:

            print(
                "❌ SKU не е намерено във variants[]:",
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
        # PRINT VARIANT INFO
        # -------------------------------------------------

        print_variant_info(
            variant
        )


        # -------------------------------------------------
        # QUANTITY
        # -------------------------------------------------

        quantity = extract_variant_quantity(
            variant
        )


        if quantity is not None:

            print(
                "📦 Крайно количество:",
                quantity
            )

        else:

            print(
                "⚠️ Quantity не е намерено"
            )


        # -------------------------------------------------
        # AVAILABILITY
        # -------------------------------------------------

        availability = extract_variant_availability(
            variant
        )


        print(
            "📊 Наличност:",
            availability
        )


        # -------------------------------------------------
        # PRICE
        # -------------------------------------------------

        price = extract_variant_price_from_data(
            variant
        )


        if price:

            print(
                "💰 Крайна цена:",
                price
            )

        else:

            print(
                "❌ Няма намерена цена"
            )


        # -------------------------------------------------
        # SAVE RESULT
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


            print(
                "✅ Записан резултат:",
                sku,
                availability,
                quantity,
                price
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
        "📁 Debug:",
        DEBUG_DIR
    )


    print(
        "✅ Готово"
    )


if __name__ == "__main__":

    main()
