#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# === Playwright вариант, базиран на предишния работещ Selenium скрипт ===
# - Търси през /search?term=<sku>, събира кандидат продуктови линкове.
# - Отваря продуктите, намира точния ред по "КОД" в #fast-order-table и:
#     * Цена: нормалната (от <strike> ако има; иначе първата "... лв./€" в реда)
#     * Наличност: ако редът съдържа tooltip "Изчерпан продукт!" / email иконата → "Изчерпан", иначе "Наличен"
# - Не чете бройки (пише "-" за колона "Бройки").

import csv
import os
import re
import time
import random
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SKU_CSV = os.path.join(BASE_DIR, "sku_list_filstar.csv")

RESULT_CSV = os.path.join(BASE_DIR, "results_filstar.csv")
NOT_FOUND_CSV = os.path.join(BASE_DIR, "not_found_filstar.csv")

DEBUG_DIR = os.path.join(BASE_DIR, "debug_html")

os.makedirs(DEBUG_DIR, exist_ok=True)


BASE_URL = "https://filstar.com"
SEARCH_URL = BASE_URL + "/search?term={q}"

WAIT_MIN = 1
WAIT_MAX = 2

PAGE_TIMEOUT = 30000
MAX_CANDIDATES = 12



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



def only_digits(s):
    return re.sub(r"\D+", "", s or "")



def read_skus():

    result = []
    block = False

    with open(SKU_CSV, encoding="utf-8-sig") as f:
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

    with open(RESULT_CSV, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["SKU", "Наличност", "Бройки", "Цена"])

    with open(NOT_FOUND_CSV, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["SKU"])



def save_result(row):
    with open(RESULT_CSV, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)



def save_not_found(sku):
    with open(NOT_FOUND_CSV, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([sku])



def get_search_candidates(page, sku):

    url = SEARCH_URL.format(q=sku)

    print("🌐 SEARCH:", url)

    try:
        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT
        )
    except Exception as e:
        print("⚠️ Timeout при търсене:", e)
        return []

    time.sleep(1)

    debug(f"search_{sku}.html", page.content())

    links = []

    for sel in (
        ".product-item-wapper a.product-name",
        ".product-title a"
    ):
        try:
            for a in page.query_selector_all(sel):
                href = a.get_attribute("href")
                if href:
                    if href.startswith("/"):
                        href = urljoin(BASE_URL, href)
                    links.append(href)
        except Exception:
            pass

    seen = set()
    uniq = []
    for h in links:
        if h not in seen:
            seen.add(h)
            uniq.append(h)

    print("🔗 Кандидати:", len(uniq))

    return uniq[:MAX_CANDIDATES]



def extract_from_product_page(page, sku):

    try:
        page.wait_for_selector(
            "#fast-order-table tbody",
            timeout=PAGE_TIMEOUT
        )
    except Exception:
        return None, None, None

    rows = page.query_selector_all("#fast-order-table tbody tr")

    target = None

    for row in rows:
        try:
            code_el = row.query_selector("td.td-sky")
            if code_el and only_digits(code_el.inner_text().strip()) == str(sku):
                target = row
                break
        except Exception:
            continue

    if target is None:
        for row in rows:
            try:
                text = row.inner_text()
                if re.search(rf"\b{re.escape(str(sku))}\b", text):
                    target = row
                    break
            except Exception:
                continue

    if target is None:
        return None, None, None

    row_text = target.inner_text()

    # --- Цена (от <strike> ако има, иначе първата в реда) ---
    price = None

    try:
        strike_el = target.query_selector("strike")
        if strike_el:
            m = re.search(r"(\d+[.,]?\d*)\s*(€|лв)", strike_el.inner_text())
            if m:
                price = m.group(1).replace(",", ".")
    except Exception:
        pass

    if price is None:
        m2 = re.search(r"(\d+[.,]?\d*)\s*(€|лв)", row_text)
        if m2:
            price = m2.group(1).replace(",", ".")

    # --- Наличност само по tooltip/email/текст ---
    status = "Наличен"

    try:
        if target.query_selector("[data-target='#send-request']"):
            status = "Изчерпан"
        elif "Изчерпан продукт!" in row_text:
            status = "Изчерпан"
        else:
            cart_icon = target.query_selector(
                ".custom-tooltip-holder img[alt='Shopping cart']"
            )
            if cart_icon:
                status = "Изчерпан"
    except Exception:
        pass

    return status, "-", price



def process_one_sku(page, sku):

    print("================")
    print("➡️ SKU:", sku)

    candidates = get_search_candidates(page, sku)

    if not candidates:
        print("❌ Няма резултат от търсенето")
        save_not_found(sku)
        return

    for link in candidates:

        try:
            page.goto(
                link,
                wait_until="domcontentloaded",
                timeout=PAGE_TIMEOUT
            )
        except Exception as e:
            print("⚠️ Timeout при зареждане на продукт:", e)
            continue

        time.sleep(1)

        status, qty, price = extract_from_product_page(page, sku)

        if price is not None:
            print(f"✅ {sku} → {price} | {status} | {link}")
            save_result([sku, status, qty, price])
            return

    debug(f"not_found_{sku}.html", page.content())
    print("❌ Няма цена/ред за този SKU")
    save_not_found(sku)



def main():

    init_csv()

    skus = read_skus()

    print("Общо SKU:", len(skus))

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
            locale="bg-BG",
            timezone_id="Europe/Sofia",
            viewport={"width": 1366, "height": 900}
        )

        page = context.new_page()

        print("🌐 Зареждам Filstar...")

        try:
            page.goto(
                BASE_URL,
                wait_until="domcontentloaded",
                timeout=PAGE_TIMEOUT
            )
        except Exception as e:
            print("⚠️ Timeout при зареждане:", e)

        time.sleep(3)

        print("🍪 Cookies:", len(context.cookies()))

        for sku in skus:
            process_one_sku(page, sku)
            time.sleep(random.uniform(WAIT_MIN, WAIT_MAX))

        browser.close()

    print("✅ Готово")



if __name__ == "__main__":
    main()
