#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import re
import time
import random

from playwright.sync_api import sync_playwright


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SKU_CSV = os.path.join(BASE_DIR, "sku_list_filstar.csv")

RESULT_CSV = os.path.join(BASE_DIR, "results_filstar.csv")
NOT_FOUND_CSV = os.path.join(BASE_DIR, "not_found_filstar.csv")

DEBUG_DIR = os.path.join(BASE_DIR, "debug_html")

os.makedirs(DEBUG_DIR, exist_ok=True)


BASE_URL = "https://filstar.com"

WAIT_MIN = 3
WAIT_MAX = 6



def debug(name, data):

    try:
        with open(
            os.path.join(DEBUG_DIR, name),
            "w",
            encoding="utf-8"
        ) as f:
            f.write(data)

        print("🐞 Debug:", name)

    except:
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




def search_product(page, sku):

    url = f"{BASE_URL}/api/search?term={sku}"

    print(
        "🌐 SEARCH:",
        url
    )


    html = page.evaluate(
        """
        async(url)=>{

            let r = await fetch(url,{
                headers:{
                    "X-Requested-With":"XMLHttpRequest"
                }
            });

            return await r.text();

        }
        """,
        url
    )


    debug(
        f"search_{sku}.html",
        html
    )


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


    return ids[0] if ids else None




def get_product_page(page, product_id):


    url = f"{BASE_URL}/product/{product_id}"


    print(
        "🌐 PRODUCT:",
        url
    )


    page.goto(
        url,
        wait_until="networkidle",
        timeout=60000
    )


    time.sleep(3)


    html = page.content()


    if (
        "Изпълняваме проверка за сигурност" in html
        or
        "Just a moment" in html
    ):

        print(
            "⚠️ Cloudflare challenge"
        )

        return None



    debug(
        f"product_{product_id}.html",
        html
    )


    return html




def extract_price(html):


    patterns = [

        r'discount-price".*?([\d]+\.[\d]{2})\s*лв',

        r'([\d]+\.[\d]{2})\s*лв\.',

        r'"price"\s*:\s*"([\d\.]+)"',

        r'"price"\s*:\s*([\d\.]+)'

    ]


    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            re.I | re.S
        )

        if match:

            return match.group(1)


    return None




def main():

    init_csv()


    skus = read_skus()


    print(
        "Общо SKU:",
        len(skus)
    )


    with sync_playwright() as p:


        browser = p.chromium.launch(
            headless=True
        )


        context = browser.new_context(

            user_agent=
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128 Safari/537.36",

            locale="bg-BG",

            timezone_id="Europe/Sofia",

            viewport={
                "width":1366,
                "height":768
            }

        )


        page = context.new_page()


        print(
            "🌐 Зареждам Filstar..."
        )


         try:
        page.goto(
            url,
            wait_until="networkidle",
            timeout=90000
        )

    except Exception as e:
        print(
            "⚠️ Timeout при зареждане:",
            e
        )
        time.sleep(5)


        print(
            "🍪 Cookies:",
            len(context.cookies())
        )


        for sku in skus:


            print("================")


            print(
                "➡️ SKU:",
                sku
            )


            product_id = search_product(
                page,
                sku
            )


            if not product_id:

                print(
                    "❌ Няма продукт"
                )

                save_not_found(sku)

                continue



            print(
                "✅ Product ID:",
                product_id
            )



            html = get_product_page(
                page,
                product_id
            )



            if not html:

                save_not_found(sku)

                continue



            price = extract_price(
                html
            )



            if price:


                print(
                    "✅ Цена:",
                    price
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


                save_not_found(sku)



            time.sleep(
                random.randint(
                    WAIT_MIN,
                    WAIT_MAX
                )
            )



        browser.close()



    print(
        "✅ Готово"
    )




if __name__ == "__main__":
    main()
