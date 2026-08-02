#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import re
import time
import requests

from bs4 import BeautifulSoup
from urllib.parse import urljoin


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SKU_CSV = os.path.join(BASE_DIR, "sku_list_filstar.csv")
RES_CSV = os.path.join(BASE_DIR, "results_filstar.csv")
NF_CSV = os.path.join(BASE_DIR, "not_found_filstar.csv")

DEBUG_DIR = os.path.join(BASE_DIR, "debug_html")

os.makedirs(DEBUG_DIR, exist_ok=True)


HEADERS = {
    "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120 Safari/537.36"
}


SEARCH_URL = "https://filstar.com/api/search?term={}"

SERIAL_URL = "https://filstar.com/get-serialize-product/{}"


WAIT = 2



def save_debug(name, data):

    path = os.path.join(
        DEBUG_DIR,
        name
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(data)

    print("🐞 Debug:", path)




def read_skus():

    result=[]

    comment=False


    with open(
        SKU_CSV,
        encoding="utf-8-sig"
    ) as f:


        for line in f:

            v=line.strip()


            if not v:
                continue


            if v.upper()=="SKU":
                continue


            if v=="##":

                comment = not comment
                continue


            if comment:
                continue


            result.append(v)



    return result




def init_files():

    with open(
        RES_CSV,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        csv.writer(f).writerow(
            [
                "SKU",
                "Наличност",
                "Цена",
                "URL"
            ]
        )


    with open(
        NF_CSV,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        csv.writer(f).writerow(
            ["SKU"]
        )




def append_result(row):

    with open(
        RES_CSV,
        "a",
        newline="",
        encoding="utf-8"
    ) as f:

        csv.writer(f).writerow(row)




def append_nf(sku):

    with open(
        NF_CSV,
        "a",
        newline="",
        encoding="utf-8"
    ) as f:

        csv.writer(f).writerow([sku])





def find_product(sku):

    url = SEARCH_URL.format(sku)


    print("🌐",url)


    r=requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )


    print(
        "STATUS:",
        r.status_code,
        "SIZE:",
        len(r.text)
    )


    save_debug(
        f"search_{sku}.html",
        r.text
    )


    soup=BeautifulSoup(
        r.text,
        "html.parser"
    )


    product=None


    for a in soup.select(
        ".product-name"
    ):

        href=a.get("href")


        if href:

            product=urljoin(
                "https://filstar.com",
                href
            )

            break



    if not product:

        return None



    print(
        "➡️ PRODUCT:",
        product
    )


    return product





def find_product_id(html):


    patterns=[

        r'data-product-id="(\d+)"',

        r'product_id.?(\d+)',

        r'productId.?(\d+)',

        r'/get-serialize-product/(\d+)'

    ]


    for p in patterns:

        m=re.search(
            p,
            html
        )

        if m:

            return m.group(1)



    return None





def get_serialized(product_id):


    url=SERIAL_URL.format(
        product_id
    )


    print(
        "🔗 SERIAL:",
        url
    )


    r=requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )


    print(
        "SERIAL STATUS:",
        r.status_code,
        "SIZE:",
        len(r.text)
    )


    save_debug(
        f"serialize_{product_id}.html",
        r.text
    )


    return r.text





def parse_data(html,sku):


    price=None


    m=re.search(
        r'(\d+[.,]\d+)\s*(?:лв|€)',
        html
    )


    if m:

        price=m.group(1).replace(",", ".")



    status="Наличен"


    if (
        "Изчерпан" in html
        or
        "out-of-stock" in html
    ):

        status="Изчерпан"



    return status,price






def main():

    init_files()


    skus=read_skus()


    print(
        "🧾 SKU:",
        len(skus)
    )


    for sku in skus:


        print("\n================")
        print("➡️ SKU:",sku)



        product=find_product(sku)


        if not product:

            print("❌ няма продукт")

            append_nf(sku)

            continue



        # пробваме да вземем ID от search HTML

        search_html=open(
            os.path.join(
                DEBUG_DIR,
                f"search_{sku}.html"
            ),
            encoding="utf-8"
        ).read()


        product_id=find_product_id(
            search_html
        )


        if not product_id:


            print(
                "❌ няма product ID"
            )

            append_nf(sku)

            continue



        serialize=get_serialized(
            product_id
        )


        status,price=parse_data(
            serialize,
            sku
        )


        if price:

            print(
                "✅",
                price,
                status
            )


            append_result(
                [
                    sku,
                    status,
                    price,
                    product
                ]
            )


        else:

            print(
                "❌ няма цена"
            )

            append_nf(sku)



        time.sleep(WAIT)




if __name__=="__main__":

    main()
