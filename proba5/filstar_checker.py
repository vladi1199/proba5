#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import re
import time
import json
import requests

from urllib.parse import urljoin

from playwright.sync_api import sync_playwright


# ================= PATHS =================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

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


# ================= SETTINGS =================

BASE_URL = "https://filstar.com"

SEARCH_URL = (
    "https://filstar.com/api/search?term={}"
)

PRODUCT_JSON_URL = (
    "https://filstar.com/get-serialize-product/{}"
)

WAIT_TIME = 1


# ================= SESSION =================

session = requests.Session()


session.headers.update(
    {
        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "Chrome/120 Safari/537.36"
    }
)



# ================= DEBUG =================

def save_debug(filename, content):

    path = os.path.join(
        DEBUG_DIR,
        filename
    )

    try:

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(content)


        print(
            f"🐞 Debug: {path}"
        )

    except:

        pass



# ================= CSV =================


def read_skus():

    skus = []

    comment_block = False


    with open(
        SKU_CSV,
        "r",
        encoding="utf-8-sig"
    ) as file:


        for line in file:


            value = line.strip()


            if not value:
                continue


            if value.upper() == "SKU":
                continue


            if value == "##":

                comment_block = not comment_block
                continue


            if comment_block:
                continue


            skus.append(value)


    return skus



def init_csv():

    with open(
        RESULT_CSV,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        csv.writer(file).writerow(
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
    ) as file:

        csv.writer(file).writerow(
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
    ) as file:

        csv.writer(file).writerow(row)



def save_not_found(sku):

    with open(
        NOT_FOUND_CSV,
        "a",
        newline="",
        encoding="utf-8"
    ) as file:

        csv.writer(file).writerow(
            [
                sku
            ]
        )



# ================= BROWSER COOKIES =================


def load_browser_cookies():

    print(
        "🌐 Зареждам Filstar през браузър..."
    )


    with sync_playwright() as p:


        browser = p.chromium.launch(
            headless=True
        )


        context = browser.new_context(
            user_agent=
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "Chrome/120 Safari/537.36"
        )


        page = context.new_page()


        page.goto(
            BASE_URL,
            wait_until="domcontentloaded",
            timeout=30000
        )


        time.sleep(3)


        cookies = context.cookies()


        browser.close()



    for c in cookies:

        session.cookies.set(
            c["name"],
            c["value"],
            domain=c["domain"]
        )


    print(
        f"🍪 Заредени cookies: {len(cookies)}"
    )



# ================= SEARCH =================


def find_product_id(sku):


    url = SEARCH_URL.format(
        sku
    )


    print(
        f"🌐 SEARCH: {url}"
    )


    session.headers.update(
        {
            "Referer": BASE_URL + "/",
            "Accept":
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
    )


    response = session.get(
        url,
        timeout=30
    )


    print(
        f"STATUS: {response.status_code} SIZE: {len(response.text)}"
    )


    save_debug(
        f"search_{sku}.html",
        response.text
    )


    if response.status_code != 200:

        return None



    patterns = [

        r'/get-serialize-product/(\d+)',

        r'data-product-id="(\d+)"',

        r'product-id="(\d+)"'

    ]


    for pattern in patterns:


        match = re.search(
            pattern,
            response.text
        )


        if match:


            product_id = match.group(1)


            print(
                f"✅ Product ID: {product_id}"
            )


            return product_id



    print(
        "❌ Няма Product ID"
    )


    return None



# ================= JSON =================


def get_product_json(product_id):


    url = PRODUCT_JSON_URL.format(
        product_id
    )


    print(
        f"📦 JSON: {url}"
    )


    session.headers.update(
        {
            "Referer":
            BASE_URL + "/",

            "Accept":
            "application/json, text/javascript, */*; q=0.01",

            "X-Requested-With":
            "XMLHttpRequest"
        }
    )


    response = session.get(
        url,
        timeout=30
    )


    print(
        f"JSON STATUS: {response.status_code}"
    )


    save_debug(
        f"json_{product_id}.html",
        response.text
    )


    if response.status_code != 200:

        return None



    try:

        return response.json()


    except:

        return None



# ================= EXTRACT =================


def extract_price(data):


    if not data:

        return None



    try:


        price = data.get(
            "price"
        )


        if price:

            return str(price)



        default = data.get(
            "defaultVariant"
        )


        if default:

            price = default.get(
                "price"
            )


            if price:

                return str(price)



    except:

        pass



    return None



# ================= MAIN =================


def main():


    init_csv()


    skus = read_skus()


    print(
        f"🧾 Общо SKU: {len(skus)}"
    )


    load_browser_cookies()



    for sku in skus:


        print("================")

        print(
            f"➡️ SKU: {sku}"
        )


        product_id = find_product_id(
            sku
        )


        if not product_id:


            save_not_found(
                sku
            )

            continue



        data = get_product_json(
            product_id
        )


        price = extract_price(
            data
        )


        if price:


            print(
                f"✅ Цена: {price}"
            )


            save_result(
                [
                    sku,
                    "Наличен",
                    "-",
                    price
                ]
            )


        else:


            print(
                "❌ Няма цена"
            )


            save_not_found(
                sku
            )


        time.sleep(
            WAIT_TIME
        )



    print(
        "✅ Готово"
    )



if __name__ == "__main__":

    main()
