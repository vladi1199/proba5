#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import re
import time
import json

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

WAIT_TIME = 2



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


    except Exception:
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


        writer = csv.writer(file)


        writer.writerow(
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


        writer = csv.writer(file)


        writer.writerow(
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



# ================= SEARCH =================


def find_product_id(page, sku):


    url = SEARCH_URL.format(
        sku
    )


    print(
        f"🌐 SEARCH: {url}"
    )


    try:

        html = page.evaluate(
            """
            async (url) => {

                const response = await fetch(
                    url,
                    {
                        headers:{
                            "X-Requested-With":"XMLHttpRequest"
                        }
                    }
                );

                return await response.text();
            }
            """,
            url
        )


    except Exception as e:

        print(
            f"SEARCH ERROR: {e}"
        )

        return None



    save_debug(
        f"search_{sku}.html",
        html
    )


    print(
        f"STATUS: 200 SIZE: {len(html)}"
    )



    # намиране на product URL

    urls = re.findall(
        r'href="([^"]+)"',
        html
    )


    product_urls = []


    for u in urls:

        if (
            "filstar.com/" in u
            and "api" not in u
        ):

            full = urljoin(
                BASE_URL,
                u
            )

            if full not in product_urls:

                product_urls.append(full)



    if not product_urls:

        print(
            "❌ Няма продукт"
        )

        return None



    product_url = product_urls[0]


    print(
        f"➡️ PRODUCT PAGE: {product_url}"
    )


    # взимаме ID от страницата

    page.goto(
        product_url,
        wait_until="domcontentloaded",
        timeout=60000
    )


    time.sleep(2)



    html = page.content()



    match = re.search(
        r'product(?:-|_)?id["\']?\s*[:=]\s*["\']?(\d+)',
        html,
        re.I
    )


    if match:

        return match.group(1)



    # fallback от URL scripts

    match = re.search(
        r'get-serialize-product/(\d+)',
        html
    )


    if match:

        return match.group(1)



    return None



# ================= JSON =================


def get_product_json(page, product_id):


    url = PRODUCT_JSON_URL.format(
        product_id
    )


    print(
        f"📦 JSON: {url}"
    )


    try:


        result = page.evaluate(
            """
            async (url)=>{

                const response = await fetch(
                    url,
                    {
                        method:"GET",
                        headers:{
                            "X-Requested-With":"XMLHttpRequest",
                            "Accept":"application/json"
                        }
                    }
                );


                return await response.text();

            }
            """,
            url
        )



        save_debug(
            f"json_{product_id}.html",
            result
        )



        return json.loads(
            result
        )



    except Exception as e:


        print(
            f"JSON ERROR: {e}"
        )


        return None




# ================= PRICE =================


def extract_price(data):


    if not data:
        return None



    try:

        price = data.get(
            "price"
        )


        if price:

            return str(price)



        variant = data.get(
            "defaultVariant"
        )


        if variant:

            return str(
                variant.get("price")
            )



    except Exception:

        pass



    return None




# ================= MAIN =================


def main():


    init_csv()


    skus = read_skus()


    print(
        f"Общо SKU: {len(skus)}"
    )



    with sync_playwright() as p:


        browser = p.chromium.launch(
            headless=True
        )


        context = browser.new_context(
            user_agent=
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120 Safari/537.36"
        )


        page = context.new_page()



        print(
            "🌐 Зареждам Filstar през браузър..."
        )


        page.goto(
            BASE_URL,
            wait_until="networkidle",
            timeout=60000
        )


        time.sleep(5)



        cookies = context.cookies()


        print(
            f"🍪 Заредени cookies: {len(cookies)}"
        )



        for sku in skus:


            print("================")


            print(
                f"➡️ SKU: {sku}"
            )



            product_id = find_product_id(
                page,
                sku
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
                f"✅ Product ID: {product_id}"
            )



            data = get_product_json(
                page,
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



        browser.close()



    print(
        "✅ Готово"
    )



if __name__ == "__main__":

    main()
