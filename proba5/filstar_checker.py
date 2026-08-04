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

WAIT_TIME = 3



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


    except:
        pass




# ================= CSV =================


def read_skus():

    result = []

    block = False


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

                block = not block
                continue


            if block:
                continue


            result.append(value)


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




# ================= RESPONSE LISTENER =================


captured_json = {}



def handle_response(response):

    global captured_json


    url = response.url


    if "/get-serialize-product/" in url:


        print(
            f"📦 Хванат JSON: {url}"
        )


        try:

            body = response.text()


            save_debug(
                "captured_json.html",
                body
            )


            captured_json[url] = body


        except Exception as e:

            print(
                e
            )





# ================= SEARCH =================


def search_product(page, sku):


    url = SEARCH_URL.format(
        sku
    )


    print(
        f"🌐 SEARCH: {url}"
    )


    captured_json.clear()



    try:

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000
        )


    except Exception as e:

        print(
            f"SEARCH PAGE ERROR: {e}"
        )



    time.sleep(3)



    html = page.content()



    save_debug(
        f"search_{sku}.html",
        html
    )



    ids = re.findall(
        r'"id"\s*:\s*(\d+)',
        html
    )



    if ids:


        print(
            f"✅ Product ID: {ids[0]}"
        )


        return ids[0]



    return None





# ================= PRODUCT =================


def load_product(page, product_id):


    url = (
        f"https://filstar.com/get-serialize-product/{product_id}"
    )


    print(
        f"📦 Зареждам JSON: {url}"
    )


    captured_json.clear()



    try:

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000
        )


    except Exception as e:

        print(
            e
        )



    time.sleep(2)



    if captured_json:


        body = list(
            captured_json.values()
        )[0]


        try:

            return json.loads(body)


        except:

            pass



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

        return str(
            data["defaultVariant"]["price"]
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
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        )



        page = context.new_page()



        page.on(
            "response",
            handle_response
        )



        print(
            "🌐 Отварям Filstar..."
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



            product_id = search_product(
                page,
                sku
            )



            if not product_id:


                print(
                    "❌ Няма продукт"
                )


                save_not_found(
                    sku
                )

                continue



            data = load_product(
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
