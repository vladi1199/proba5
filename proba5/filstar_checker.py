import csv
import json
import os
import re
import time

import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# ============================================================
# НАСТРОЙКИ
# ============================================================

BASE_URL = "https://filstar.com"

SEARCH_URL = BASE_URL + "/api/search?term={}"
PRODUCT_URL = BASE_URL + "/get-serialize-product/{}"

INPUT_CSV = "sku_list_filstar.csv"
RESULTS_CSV = "results_filstar.csv"
NOT_FOUND_CSV = "not_found_filstar.csv"

DEBUG_DIR = "debug_html"

# Пауза между продуктите
WAIT = 2

# Колко време да чакаме Cloudflare да приключи
CLOUDFLARE_WAIT = 30


# ============================================================
# ПОДГОТОВКА
# ============================================================

os.makedirs(DEBUG_DIR, exist_ok=True)


# ============================================================
# REQUESTS SESSION
# Използва се само за SEARCH API
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "application/json,text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "bg-BG,bg;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": BASE_URL + "/",
})


# ============================================================
# CLOUDFLARE ПРОВЕРКА
# ============================================================

def is_cloudflare_page(text):
    """
    Проверява дали отговорът е Cloudflare challenge.
    """

    if not text:
        return False

    indicators = [
        "Just a moment...",
        "Enable JavaScript and cookies to continue",
        "challenge-platform",
        "cdn-cgi/challenge-platform",
        "cf_chl_opt",
        "cf_chl_",
        "Cloudflare",
    ]

    text_lower = text.lower()

    for indicator in indicators:
        if indicator.lower() in text_lower:
            return True

    return False


# ============================================================
# ЧЕТЕНЕ НА SKU CSV
# ============================================================

def read_skus():

    skus = []

    if not os.path.exists(INPUT_CSV):

        print(
            f"❌ Липсва файл: {INPUT_CSV}"
        )

        return skus

    with open(
        INPUT_CSV,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            sku = str(
                row.get("SKU", "")
            ).strip()

            if sku:
                skus.append(sku)

    return skus


# ============================================================
# НАМИРАНЕ НА PRODUCT ID ОТ SEARCH
# ============================================================

def find_product_id_from_search(html, sku):

    candidates = []

    # --------------------------------------------------------
    # 1. Опит като JSON
    # --------------------------------------------------------

    try:

        data = json.loads(html)

        json_objects = []

        if isinstance(data, list):

            json_objects = data

        elif isinstance(data, dict):

            # Проверяваме най-често срещаните структури
            for key in [
                "products",
                "items",
                "results",
                "data",
            ]:

                value = data.get(key)

                if isinstance(value, list):

                    json_objects.extend(value)

                elif isinstance(value, dict):

                    json_objects.append(value)

        print(
            f"🔍 JSON обекти: {len(json_objects)}"
        )

        for item in json_objects:

            if not isinstance(item, dict):
                continue

            # ------------------------------------------------
            # Търсим SKU вътре в обекта
            # ------------------------------------------------

            item_text = json.dumps(
                item,
                ensure_ascii=False
            )

            if str(sku) not in item_text:
                continue

            product_id = (
                item.get("id")
                or item.get("productId")
                or item.get("product_id")
            )

            if product_id:

                product_id = str(product_id)

                if product_id not in candidates:

                    candidates.append(
                        product_id
                    )

    except Exception:

        pass


    # --------------------------------------------------------
    # 2. HTML / REGEX FALLBACK
    # --------------------------------------------------------

    if not candidates:

        patterns = [

            r'data-product-id=["\'](\d+)',

            r'"productId"\s*:\s*["\']?(\d+)',

            r'"product_id"\s*:\s*["\']?(\d+)',

        ]

        for pattern in patterns:

            found = re.findall(
                pattern,
                html,
                flags=re.I
            )

            for value in found:

                if value not in candidates:

                    candidates.append(value)


    print(
        f"ID кандидати: {candidates}"
    )

    if candidates:

        return candidates[0]

    return None


# ============================================================
# ПРОВЕРКА НА PRODUCT JSON
# ============================================================

def looks_like_product_json(data):

    if not isinstance(data, dict):
        return False

    # Реалният product response има variants
    if isinstance(
        data.get("variants"),
        list
    ):

        return True

    # Допълнителен fallback
    if (
        "id" in data
        and "name" in data
    ):

        return True

    return False


# ============================================================
# ИЗВЛИЧАНЕ НА JSON ОТ PAGE
# ============================================================

def extract_product_json(page):

    # --------------------------------------------------------
    # Вариант 1:
    # body text
    # --------------------------------------------------------

    try:

        body_text = page.locator(
            "body"
        ).inner_text(
            timeout=5000
        ).strip()

        if body_text:

            try:

                data = json.loads(
                    body_text
                )

                if looks_like_product_json(data):

                    return data

            except Exception:

                pass

    except Exception:

        pass


    # --------------------------------------------------------
    # Вариант 2:
    # page content
    # --------------------------------------------------------

    try:

        html = page.content()

        # Ако е JSON директно
        try:

            data = json.loads(
                html
            )

            if looks_like_product_json(data):

                return data

        except Exception:

            pass

    except Exception:

        pass


    # --------------------------------------------------------
    # Вариант 3:
    # Търсим JSON в body
    # --------------------------------------------------------

    try:

        html = page.content()

        match = re.search(
            r"<body[^>]*>(.*?)</body>",
            html,
            flags=re.I | re.S
        )

        if match:

            body = match.group(1)

            # Премахваме HTML
            from bs4 import BeautifulSoup

            text = BeautifulSoup(
                body,
                "html.parser"
            ).get_text(
                "\n"
            ).strip()

            if text:

                try:

                    data = json.loads(text)

                    if looks_like_product_json(data):

                        return data

                except Exception:

                    pass

    except Exception:

        pass


    return None


# ============================================================
# ИЗЧАКВАНЕ НА CLOUDFLARE
# ============================================================

def wait_for_cloudflare(page, product_id):

    print(
        "⏳ Проверка за Cloudflare..."
    )

    start_time = time.time()

    last_status = None

    while True:

        elapsed = time.time() - start_time

        if elapsed >= CLOUDFLARE_WAIT:

            break

        try:

            html = page.content()

        except Exception:

            html = ""

        cloudflare = is_cloudflare_page(
            html
        )

        if cloudflare:

            if last_status != "cloudflare":

                print(
                    "🛡️ Cloudflare Challenge..."
                )

                last_status = "cloudflare"

            time.sleep(2)

            continue


        # ----------------------------------------------------
        # Проверяваме дали вече имаме JSON
        # ----------------------------------------------------

        data = extract_product_json(
            page
        )

        if data:

            print(
                "✅ Product JSON получен"
            )

            return data


        if last_status != "waiting":

            print(
                "⏳ Чакаме product JSON..."
            )

            last_status = "waiting"

        time.sleep(1)


    # --------------------------------------------------------
    # Последен опит
    # --------------------------------------------------------

    data = extract_product_json(
        page
    )

    if data:

        print(
            "✅ Product JSON получен"
        )

        return data


    # --------------------------------------------------------
    # DEBUG
    # --------------------------------------------------------

    try:

        html = page.content()

        debug_file = os.path.join(
            DEBUG_DIR,
            f"product_{product_id}_error.html"
        )

        with open(
            debug_file,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(html)

        print(
            f"🐞 Debug: product_{product_id}_error.html"
        )

    except Exception:

        pass


    return None


# ============================================================
# ВЗИМАНЕ НА PRODUCT DATA
# ============================================================

def get_product_data(page, product_id):

    product_url = PRODUCT_URL.format(
        product_id
    )

    print(
        f"📦 PRODUCT: {product_url}"
    )

    try:

        # ----------------------------------------------------
        # Отваряме product endpoint
        # ----------------------------------------------------

        response = page.goto(
            product_url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        if response:

            print(
                f"📡 Product HTTP: "
                f"{response.status}"
            )

        else:

            print(
                "📡 Product HTTP: unknown"
            )


        # ----------------------------------------------------
        # Изчакваме Cloudflare / JSON
        # ----------------------------------------------------

        data = wait_for_cloudflare(
            page,
            product_id
        )

        return data


    except PlaywrightTimeoutError:

        print(
            "⚠️ Page timeout"
        )

        try:

            html = page.content()

            debug_file = os.path.join(
                DEBUG_DIR,
                f"product_{product_id}_timeout.html"
            )

            with open(
                debug_file,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(html)

            print(
                f"🐞 Debug: product_{product_id}_timeout.html"
            )

        except Exception:

            pass

        return None


    except Exception as e:

        print(
            f"❌ Product Playwright Error: {e}"
        )

        return None


# ============================================================
# НАМИРАНЕ НА VARIANT ПО SKU
# ============================================================

def find_variant(product_data, sku):

    if not isinstance(
        product_data,
        dict
    ):

        return None


    variants = product_data.get(
        "variants",
        []
    )

    if not isinstance(
        variants,
        list
    ):

        return None


    for variant in variants:

        if not isinstance(
            variant,
            dict
        ):

            continue


        variant_sku = str(
            variant.get(
                "sku",
                ""
            )
        ).strip()


        if variant_sku == str(
            sku
        ).strip():

            return variant


    return None


# ============================================================
# ОБЩО КОЛИЧЕСТВО
# ============================================================

def get_total_quantity(variant):

    # --------------------------------------------------------
    # При Filstar имаме:
    #
    # "stores": [
    #     {"quantity": 1},
    #     {"quantity": 0}
    # ]
    #
    # Искаме:
    #
    # 1 + 0 = 1
    # --------------------------------------------------------

    stores = variant.get(
        "stores"
    )


    if isinstance(
        stores,
        list
    ):

        total = 0

        for store in stores:

            if not isinstance(
                store,
                dict
            ):

                continue

            quantity = store.get(
                "quantity",
                0
            )

            try:

                total += int(
                    quantity or 0
                )

            except (
                ValueError,
                TypeError
            ):

                pass


        return total


    # --------------------------------------------------------
    # Fallback:
    # Ако няма stores, използваме variant.quantity
    # --------------------------------------------------------

    quantity = variant.get(
        "quantity",
        0
    )

    try:

        return int(
            quantity or 0
        )

    except (
        ValueError,
        TypeError
    ):

        return 0


# ============================================================
# ЦЕНА
# ============================================================

def get_price(variant):

    # Приоритет:
    #
    # discountedRetailPrice
    # discountedPrice
    # price
    #
    # За да получим реалната продажна цена.

    price = (
        variant.get(
            "discountedRetailPrice"
        )
        or variant.get(
            "discountedPrice"
        )
        or variant.get(
            "price"
        )
        or 0
    )

    try:

        return round(
            float(price),
            2
        )

    except (
        ValueError,
        TypeError
    ):

        return 0


# ============================================================
# ЗАПИС RESULTS CSV
# ============================================================

def save_results(results):

    with open(
        RESULTS_CSV,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.writer(f)

        writer.writerow([
            "SKU",
            "Наличност",
            "Цена"
        ])

        for row in results:

            writer.writerow([
                row["SKU"],
                row["Наличност"],
                row["Цена"]
            ])


# ============================================================
# ЗАПИС NOT FOUND CSV
# ============================================================

def save_not_found(not_found):

    with open(
        NOT_FOUND_CSV,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.writer(f)

        writer.writerow([
            "SKU"
        ])

        for sku in not_found:

            writer.writerow([
                sku
            ])


# ============================================================
# MAIN
# ============================================================

def main():

    skus = read_skus()

    print(
        f"Общо SKU: {len(skus)}"
    )


    if not skus:

        print(
            "❌ Няма SKU за обработка."
        )

        return


    results = []

    not_found = []


    # ========================================================
    # PLAYWRIGHT
    # ========================================================

    with sync_playwright() as p:

        print(
            "\n🌐 Стартиране на Chromium..."
        )

        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )


        context = browser.new_context(

            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),

            viewport={
                "width": 1920,
                "height": 1080
            },

            locale="bg-BG",

            timezone_id="Europe/Sofia",

            java_script_enabled=True,

            ignore_https_errors=False,
        )


        page = context.new_page()


        # ====================================================
        # SKU LOOP
        # ====================================================

        for sku in skus:

            print(
                "\n================"
            )

            print(
                f"➡️ SKU: {sku}"
            )


            # =================================================
            # SEARCH API
            # =================================================

            search_url = SEARCH_URL.format(
                sku
            )

            print(
                f"🌐 SEARCH: {search_url}"
            )


            try:

                response = session.get(
                    search_url,
                    timeout=30
                )

                print(
                    f"🔎 Search HTTP: "
                    f"{response.status_code}"
                )

                search_html = response.text


            except Exception as e:

                print(
                    f"❌ Search Error: {e}"
                )

                not_found.append(
                    sku
                )

                continue


            # ------------------------------------------------
            # DEBUG SEARCH
            # ------------------------------------------------

            search_debug = os.path.join(
                DEBUG_DIR,
                f"search_{sku}.html"
            )

            with open(
                search_debug,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(
                    search_html
                )


            print(
                f"🐞 Debug: search_{sku}.html"
            )


            # =================================================
            # PRODUCT ID
            # =================================================

            product_id = find_product_id_from_search(
                search_html,
                sku
            )


            if not product_id:

                print(
                    f"❌ Няма Product ID за SKU: {sku}"
                )

                not_found.append(
                    sku
                )

                continue


            print(
                f"✅ Product ID: {product_id}"
            )


            # =================================================
            # PRODUCT JSON
            # =================================================

            product_data = get_product_data(
                page,
                product_id
            )


            if not product_data:

                print(
                    "❌ Няма product data"
                )

                not_found.append(
                    sku
                )

                continue


            # =================================================
            # VARIANT
            # =================================================

            variant = find_variant(
                product_data,
                sku
            )


            if not variant:

                print(
                    f"❌ Няма variant за SKU: {sku}"
                )

                not_found.append(
                    sku
                )

                continue


            # =================================================
            # КОЛИЧЕСТВО
            # =================================================

            total_quantity = get_total_quantity(
                variant
            )


            # =================================================
            # ЦЕНА
            # =================================================

            price = get_price(
                variant
            )


            # =================================================
            # РЕЗУЛТАТ
            # =================================================

            print(
                f"📦 Общо количество: "
                f"{total_quantity}"
            )

            print(
                f"💰 Цена: "
                f"{price:.2f} €"
            )


            results.append({

                "SKU": sku,

                "Наличност": total_quantity,

                "Цена": price

            })


            # ------------------------------------------------
            # Пауза
            # ------------------------------------------------

            time.sleep(
                WAIT
            )


        # ====================================================
        # ЗАТВАРЯНЕ
        # ====================================================

        context.close()

        browser.close()


    # ========================================================
    # SAVE
    # ========================================================

    save_results(
        results
    )

    save_not_found(
        not_found
    )


    # ========================================================
    # SUMMARY
    # ========================================================

    print(
        "\n================"
    )

    print(
        f"✅ Обработени продукти: "
        f"{len(results)}"
    )

    print(
        f"❌ Ненамерени: "
        f"{len(not_found)}"
    )

    print(
        "✅ Готово"
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
