#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import re
import time
import json

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

WAIT_TIME = 2



# ================= DEBUG =================


def save_debug(filename, content):

    try:

        with open(
            os.path.join(DEBUG_DIR, filename),
            "w",
            encoding="utf-8"
        ) as f:

            f.write(content)


        print(
            f"🐞 Debug: {filename}"
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
    ) as f:


        for line in f:


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


        response = page.request.get(
            url,
            headers={

                "User-Agent":
                "Mozilla/5.0",

                "X-Requested-With":
                "XMLHttpRequest",

                "Accept":
                "text/html"
            }
        )



        html = response.text()



    except Exception as e:


        print(
            f"SEARCH ERROR: {e}"
        )

        return None




    print(
        f"STATUS: {response.status} SIZE: {len(html)}"
    )



    save_debug(
        f"search_{sku}.html",
        html
    )



    # директно търсим serialize endpoint

    ids = re.findall(
        r'get-serialize-product[\/\\](\d+)',
        html
    )


    if ids:

        print(
            f"✅ Product ID: {ids[0]}"
        )

        return ids[0]



    # JSON структура

    ids = re.findall(
        r'"id"\s*:\s*(\d+)',
        html
    )



    for pid in ids:


        if int(pid) > 100:


            print(
                f"✅ Product ID: {pid}"
            )


            return pid



    print(
        "❌ Product ID не е намерен"
    )


    return None





# ================= PRODUCT JSON =================


def get_product_json(page, product_id):


    url = (
        f"{BASE_URL}/get-serialize-product/{product_id}"
    )


    print(
        f"📦 JSON: {url}"
    )



    try:


        response = page.request.get(
            url,
            headers={

                "User-Agent":
                "Mozilla/5.0",

                "X-Requested-With":
                "XMLHttpRequest",

                "Accept":
                "*/*",

                "Referer":
                BASE_URL
            }
        )



        print(
            f"JSON STATUS: {response.status}"
        )



        text = response.text()



        save_debug(
            f"json_{product_id}.html",
            text
        )



        if response.status == 200:


            return json.loads(text)



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


        if data.get("price"):

            return str(
                data["price"]
            )



        variant = data.get(
            "defaultVariant"
        )


        if variant and variant.get("price"):


            return str(
                variant["price"]
            )


    except:

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
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

        )



        page = context.new_page()



        print(
            "🌐 Зареждам Filstar..."
        )


        try:


            page.goto(

                "https://filstar.com/jo-jo-klips-rapala",

                wait_until="domcontentloaded",

                timeout=60000

            )


        except Exception as e:

            print(
                e
            )



        time.sleep(5)



        print(
            f"🍪 Cookies: {len(context.cookies())}"
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


                save_not_found(
                    sku
                )

                continue




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
