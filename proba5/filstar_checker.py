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

    try:

        path = os.path.join(
            DEBUG_DIR,
            filename
        )

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
            async(url)=>{

                let r = await fetch(
                    url,
                    {
                        headers:{
                            "X-Requested-With":"XMLHttpRequest"
                        }
                    }
                );

                return await r.text();
            }
            """,
            url
        )


    except Exception as e:


        print(
            f"SEARCH ERROR {e}"
        )


        return None



    save_debug(
        f"search_{sku}.html",
        html
    )


    print(
        f"STATUS: 200 SIZE: {len(html)}"
    )


    # търсим директно endpoint ID

    ids = re.findall(
        r'get-serialize-product/(\d+)',
        html
    )


    if ids:

        return ids[0]



    # fallback product URL

    links = re.findall(
        r'href="([^"]+)"',
        html
    )


    for link in links:


        if (
            "filstar.com/" in link
            and "api" not in link
        ):


            full = urljoin(
                BASE_URL,
                link
            )


            try:

                page.goto(
                    full,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

            except:

                pass


            time.sleep(3)


            html2 = page.content()


            save_debug(
                f"product_{sku}.html",
                html2
            )


            ids = re.findall(
                r'get-serialize-product/(\d+)',
                html2
            )


            if ids:

                return ids[0]



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


        text = page.evaluate(
            """
            async(url)=>{


                let r = await fetch(
                    url,
                    {
                        headers:{
                            "X-Requested-With":"XMLHttpRequest",
                            "Accept":"application/json"
                        }
                    }
                );


                return await r.text();

            }
            """,
            url
        )



        save_debug(
            f"json_{product_id}.html",
            text
        )


        print(
            f"JSON SIZE: {len(text)}"
        )


        return json.loads(
            text
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



    if data.get("price"):

        return str(
            data["price"]
        )



    if data.get("defaultVariant"):


        price = data["defaultVariant"].get(
            "price"
        )


        if price:

            return str(
                price
            )


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


        try:

            page.goto(
                BASE_URL,
                wait_until="domcontentloaded",
                timeout=60000
            )


        except Exception as e:

            print(
                f"⚠️ Home timeout: {e}"
            )


        time.sleep(8)



        print(
            f"🍪 Заредени cookies: {len(context.cookies())}"
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
