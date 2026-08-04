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

WAIT = 3



# ================= DEBUG =================


def save_debug(name, data):

    try:

        with open(
            os.path.join(DEBUG_DIR, name),
            "w",
            encoding="utf-8"
        ) as f:

            f.write(data)


        print(
            f"🐞 Debug: {name}"
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




# ================= PRODUCT ID =================


def find_product_id(page, sku):


    url = (
        f"{BASE_URL}/api/search?term={sku}"
    )


    print(
        f"🌐 SEARCH: {url}"
    )



    try:


        response = page.request.get(
            url,
            headers={

                "Accept":
                "text/html",

                "X-Requested-With":
                "XMLHttpRequest"

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



    # всички id полета

    ids = re.findall(
        r'id["\']?\s*[:=]\s*["\']?(\d+)',
        html,
        re.I
    )



    print(
        "ID кандидати:",
        ids[:20]
    )



    for pid in ids:


        if int(pid) > 100:


            print(
                f"✅ Product ID: {pid}"
            )


            return pid



    return None





# ================= JSON =================


def get_product(page, pid):


    url = (
        f"{BASE_URL}/get-serialize-product/{pid}"
    )


    print(
        f"📦 JSON: {url}"
    )



    try:


        response = page.request.get(
            url,
            headers={

                "Accept":
                "*/*",

                "X-Requested-With":
                "XMLHttpRequest"

            }
        )


        print(
            f"JSON STATUS: {response.status}"
        )



        text = response.text()



        save_debug(
            f"json_{pid}.html",
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


def get_price(data):


    if not data:

        return None



    try:


        if data.get("defaultVariant"):


            return str(
                data["defaultVariant"]["price"]
            )



        if data.get("price"):


            return str(
                data["price"]
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
            "🌐 Отварям Filstar..."
        )



        page.goto(
            BASE_URL,
            wait_until="domcontentloaded",
            timeout=60000
        )


        time.sleep(5)



        print(
            "🍪 Cookies:",
            len(context.cookies())
        )



        for sku in skus:



            print("================")

            print(
                f"➡️ SKU: {sku}"
            )



            pid = find_product_id(
                page,
                sku
            )



            if not pid:


                print(
                    "❌ Няма Product ID"
                )


                save_not_found(
                    sku
                )


                continue



            data = get_product(
                page,
                pid
            )



            price = get_price(
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
                WAIT
            )



        browser.close()



    print(
        "✅ Готово"
    )




if __name__ == "__main__":

    main()
