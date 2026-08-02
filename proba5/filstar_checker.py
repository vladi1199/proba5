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


SEARCH_URL = "https://filstar.com/api/search?term={}"
SERIAL_URL = "https://filstar.com/get-serialize-product/{}"


WAIT = 2


# ================= SESSION =================

session = requests.Session()

session.headers.update({

    "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "Chrome/120 Safari/537.36",

    "Accept-Language":
        "bg-BG,bg;q=0.9",

    "Accept":
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"

})



# ================= DEBUG =================


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


    print(
        "🐞 Debug:",
        path
    )



# ================= CSV =================


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
            [
                "SKU"
            ]
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

        csv.writer(f).writerow(
            [sku]
        )



# ================= SKU =================


def read_skus():

    skus=[]

    comment=False


    with open(
        SKU_CSV,
        encoding="utf-8-sig"
    ) as f:


        for line in f:

            value=line.strip()


            if not value:
                continue


            if value.upper()=="SKU":
                continue


            if value=="##":

                comment = not comment
                continue


            if comment:
                continue


            skus.append(value)



    return skus



# ================= SEARCH =================


def search_product(sku):


    url = SEARCH_URL.format(
        sku
    )


    print(
        "🌐",
        url
    )


    r=session.get(
        url,
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


    if r.status_code != 200:

        return None,None



    soup=BeautifulSoup(
        r.text,
        "html.parser"
    )


    product_url=None


    for a in soup.select(
        ".product-name"
    ):

        href=a.get("href")


        if href:

            product_url=urljoin(
                "https://filstar.com",
                href
            )

            break



    if not product_url:

        return None,None



    # намиране на ID

    product_id=None


    patterns=[

        r'/get-serialize-product/(\d+)',

        r'data-product-id="(\d+)"',

        r'product_id.?(\d+)',

        r'productId.?(\d+)'

    ]


    for p in patterns:

        m=re.search(
            p,
            r.text
        )


        if m:

            product_id=m.group(1)
            break



    print(
        "➡️ PRODUCT:",
        product_url
    )

    print(
        "🆔 ID:",
        product_id
    )


    return product_url, product_id




# ================= SERIAL =================


def get_serialized(product_id, product_url):


    url=SERIAL_URL.format(
        product_id
    )


    print(
        "🔗 SERIAL:",
        url
    )


    headers={

        "Referer":
            product_url,

        "X-Requested-With":
            "XMLHttpRequest",

        "Accept":
            "application/json,"
            "text/javascript,"
            "*/*;q=0.01"

    }


    r=session.get(
        url,
        headers=headers,
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




# ================= PARSE =================


def parse_product(html):


    price=None


    m=re.search(
        r'(\d+[.,]\d+)\s*(?:лв|€)',
        html
    )


    if m:

        price=m.group(1).replace(
            ",",
            "."
        )



    status="Наличен"


    if (
        "Изчерпан" in html
        or
        "Няма наличност" in html
    ):

        status="Изчерпан"



    return status,price





# ================= MAIN =================


def main():


    init_files()


    skus=read_skus()


    print(
        "🧾 SKU:",
        len(skus)
    )



    for sku in skus:


        print("\n================")
        print(
            "➡️ SKU:",
            sku
        )


        try:


            product_url, product_id = search_product(
                sku
            )


            if not product_url or not product_id:

                print(
                    "❌ няма продукт или ID"
                )

                append_nf(
                    sku
                )

                continue



            html=get_serialized(
                product_id,
                product_url
            )


            status,price=parse_product(
                html
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
                        product_url
                    ]
                )


            else:


                print(
                    "❌ няма цена"
                )

                append_nf(
                    sku
                )



        except Exception as e:


            print(
                "ERROR:",
                e
            )

            append_nf(
                sku
            )



        time.sleep(
            WAIT
        )



    print(
        "✅ Готово"
    )



if __name__=="__main__":

    main()
