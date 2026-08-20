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


        # 43.30 лв
        r'(\d+\.\d+)\s*лв',


        # 43,30 лв
        r'(\d+,\d+)\s*лв'


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



    ids = list(dict.fromkeys(ids))


    print(
        "ID кандидати:",
        ids
    )


    if ids:

        return ids[0]


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

            save_not_found(sku)

            continue




        product_id = extract_product_id(
            html
        )



        if product_id:

            print(
                "✅ Product ID:",
                product_id
            )



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


            save_not_found(
                sku
            )



        time.sleep(WAIT)




    print(
        "✅ Готово"
    )





if __name__ == "__main__":

    main()
