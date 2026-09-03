#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import re
import time
import requests

from playwright.sync_api import sync_playwright


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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

session.headers.update(
    HEADERS
)


# =========================================================
# BROWSER (само за продуктовите страници — заради 403)
# =========================================================

_pw = None
_browser = None
_page = None


def start_browser():

    global _pw, _browser, _page

    _pw = sync_playwright().start()

    _browser = _pw.chromium.launch(
        headless=True
    )

    context = _browser.new_context(
        user_agent=HEADERS["User-Agent"],
        locale="bg-BG"
    )

    _page = context.new_page()


def stop_browser():

    global _pw, _browser

    try:

        if _browser:

            _browser.close()

    except Exception:

        pass

    try:

        if _pw:

            _pw.stop()

    except Exception:

        pass


# =========================================================
# READ SKU
# =========================================================

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


# =========================================================
# INIT CSV
# =========================================================

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


# =========================================================
# SAVE RESULT
# =========================================================

def save_result(row):

    with open(
        RESULT_CSV,
        "a",
        newline="",
        encoding="utf-8"
    ) as f:

        csv.writer(f).writerow(row)


# =========================================================
# SAVE NOT FOUND
# =========================================================

def save_not_found(sku):

    with open(
        NOT_FOUND_CSV,
        "a",
        newline="",
        encoding="utf-8"
    ) as f:

        csv.writer(f).writerow([sku])


# =========================================================
# SEARCH FILSTAR (requests — работи, 200 OK)
# =========================================================

def search_filstar(sku):

    url = f"{BASE_URL}/api/search?term={sku}"

    print("🌐 SEARCH:", url)

    try:

        r = session.get(url, timeout=30)

        print("🔎 Search HTTP:", r.status_code)

        return r.text

    except Exception as e:

        print("SEARCH ERROR:", e)

        return None


# =========================================================
# EXTRACT PRODUCT URL
# =========================================================

def extract_product_url(html):

    for match in re.finditer(r'<a\b[^>]*>', html, re.I):

        tag = match.group(0)

        if "product-name" not in tag:
            continue

        href_match = re.search(
            r'href=["\']([^"\']+)["\']',
            tag,
            re.I
        )

        if href_match:

            href = href_match.group(1)

            if href.startswith("/"):

                href = BASE_URL + href

            return href

    return None


# =========================================================
# FETCH PRODUCT PAGE (Playwright — заради 403 при requests)
# =========================================================

def fetch_product_page(url):

    try:

        _page.goto(
            url,
            timeout=30000,
            wait_until="domcontentloaded"
        )

        # опитваме да кликнем таба "Варианти", ако съществува —
        # таблицата с цени по SKU обикновено се зарежда лениво
        try:

            variant_tab = _page.get_by_text(
                "Варианти",
                exact=False
            ).first

            if variant_tab:

                variant_tab.click(timeout=5000)

        except Exception:

            pass

        # изчакваме мрежата да се успокои (AJAX зареждане на редовете)
        try:

            _page.wait_for_load_state(
                "networkidle",
                timeout=10000
            )

        except Exception:

            pass

        # допълнително изчакваме поява на текст "ЦЕНА НА ДРЕБНО"
        try:

            _page.wait_for_selector(
                "text=ЦЕНА НА ДРЕБНО",
                timeout=8000
            )

        except Exception:

            pass

        html = _page.content()

        print("🔎 Product page: OK (Playwright)")

        return html

    except Exception as e:

        print("PRODUCT PAGE ERROR:", e)

        return None


# =========================================================
# EXTRACT PRICE FOR EXACT SKU (fast-order-table)
# =========================================================

def extract_variant_price(html, sku):

    # -------------------------------------------------
    # Намираме ВСИЧКИ таблици в страницата и избираме
    # тази, чието заглавие съдържа "ЦЕНА НА ДРЕБНО"
    # (по-надеждно от фиксиран ID, който сайтът е сменил)
    # -------------------------------------------------

    tables = re.findall(
        r'<table\b[^>]*>(.*?)</table>',
        html,
        re.I | re.S
    )

    variants_table = None

    for t in tables:

        if "ЦЕНА НА ДРЕБНО" in t.upper() or "ДРЕБНО" in t.upper():

            variants_table = t

            break

    if variants_table is None:

        print("⚠️ Не намерих таблица с варианти в HTML")

        return None

    rows = re.findall(
        r'<tr\b[^>]*>(.*?)</tr>',
        variants_table,
        re.I | re.S
    )

    print(f"🔎 Намерени редове в таблицата с варианти: {len(rows)}")

    for row in rows:

        # SKU може да е в произволна клетка на реда —
        # проверяваме целия ред за точно съвпадение по цифри
        row_text_only = re.sub(r'<[^>]+>', ' ', row)

        if not re.search(rf'\b{re.escape(str(sku))}\b', row_text_only):

            continue

        price = None

        strike_match = re.search(
            r'<strike[^>]*>(.*?)</strike>',
            row,
            re.I | re.S
        )

        if strike_match:

            m = re.search(r'(\d+[.,]\d+)\s*€', strike_match.group(1))

            if m:

                price = m.group(1).replace(",", ".")

        if price is None:

            # вземаме ПОСЛЕДНОТО € число в реда (обикновено
            # "ЦЕНА НА ДРЕБНО" е последната колона)
            euro_matches = re.findall(r'(\d+[.,]\d+)\s*€', row)

            if euro_matches:

                price = euro_matches[-1].replace(",", ".")

        return price

    return None


# =========================================================
# EXTRACT PRICE (fallback — общата цена от search картона)
# =========================================================

def extract_price(html):

    patterns = [
        r'/\s*(\d+\.\d+)\s*€',
        r'/\s*(\d+,\d+)\s*€',
        r'(\d+\.\d+)\s*€',
        r'(\d+,\d+)\s*€'
    ]

    for pattern in patterns:

        m = re.search(pattern, html, re.I)

        if m:

            return m.group(1).replace(",", ".")

    return None


# =========================================================
# EXTRACT PRODUCT ID
# =========================================================

def extract_product_id(html):

    ids = re.findall(r'/get-serialize-product/(\d+)', html)

    if not ids:

        ids = re.findall(
            r'product.?id.?[:="\']+(\d+)',
            html,
            re.I
        )

    ids = list(dict.fromkeys(ids))

    print("ID кандидати:", ids)

    if ids:

        return ids[0]

    return None


# =========================================================
# EXTRACT AVAILABILITY
# =========================================================

def extract_availability(html, product_id):

    pattern = (
        r'<div\b[^>]*'
        r'class=["\'][^"\']*product-item-wapper[^"\']*["\']'
        r'[^>]*>'
    )

    matches = re.finditer(pattern, html, re.I)

    for match in matches:

        opening_tag = match.group(0)

        id_match = re.search(
            r'data-product-id=["\']'
            + re.escape(str(product_id))
            + r'["\']',
            opening_tag,
            re.I
        )

        if not id_match:

            continue

        classes_match = re.search(
            r'class=["\']([^"\']*)["\']',
            opening_tag,
            re.I
        )

        if not classes_match:

            return "Неизвестна"

        classes = classes_match.group(1).lower()

        if "out-of-stock" in classes:

            return "Неналичен"

        if "product-not-available" in classes:

            return "Неналичен"

        return "Наличен"

    return "Неизвестна"


# =========================================================
# EXTRACT QUANTITY
# =========================================================

def extract_quantity(html, sku):

    patterns = [

        r'"quantity"\s*:\s*(\d+)'
        r'.*?'
        r'"sku"\s*:\s*"'
        + re.escape(sku)
        + r'"',

        r'"sku"\s*:\s*"'
        + re.escape(sku)
        + r'"'
        r'.*?'
        r'"quantity"\s*:\s*(\d+)'

    ]

    for pattern in patterns:

        m = re.search(pattern, html, re.I | re.S)

        if m:

            return int(m.group(1))

    return None


# =========================================================
# MAIN
# =========================================================

def main():

    init_csv()

    skus = read_skus()

    print("Общо SKU:", len(skus))

    start_browser()

    try:

        for sku in skus:

            print("================")

            print("➡️ SKU:", sku)

            html = search_filstar(sku)

            if not html:

                print("❌ Няма резултат")

                save_not_found(sku)

                continue

            product_id = extract_product_id(html)

            if not product_id:

                print("❌ Няма Product ID")

                save_not_found(sku)

                time.sleep(WAIT)

                continue

            print("✅ Product ID:", product_id)

            availability = extract_availability(html, product_id)

            print("✅ Наличност:", availability)

            quantity = extract_quantity(html, sku)

            if quantity is not None:

                print("✅ Quantity:", quantity)

            else:

                print("⚠️ Quantity не е намерено")

            price = None

            product_url = extract_product_url(html)

            if product_url:

                print("🔗 Продуктова страница:", product_url)

                product_html = fetch_product_page(product_url)

                if product_html:

                    price = extract_variant_price(product_html, sku)

                    if price:

                        print("✅ Точна цена по SKU:", price)

                    else:

                        print(
                            "⚠️ SKU не е намерен в fast-order-table, "
                            "ползвам общата цена като fallback"
                        )

            else:

                print("⚠️ Няма линк към продуктова страница")

            if not price:

                price = extract_price(html)

                if price:

                    print("⚠️ Fallback обща цена:", price)

            if price:

                print("✅ Крайна цена:", price)

            else:

                print("❌ Няма намерена цена")

            if price:

                save_result(
                    [
                        sku,
                        availability,
                        quantity if quantity is not None else "-",
                        price
                    ]
                )

            else:

                save_not_found(sku)

            time.sleep(WAIT)

    finally:

        stop_browser()

    print("💾 Записани резултати:", RESULT_CSV)

    print("💾 Not found:", NOT_FOUND_CSV)

    print("✅ Готово")


if __name__ == "__main__":

    main()
