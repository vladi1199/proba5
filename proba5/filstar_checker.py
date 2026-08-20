import csv
import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


# ============================================================
# НАСТРОЙКИ
# ============================================================

BASE_URL = "https://filstar.com"

CSV_FILE = "sku_list_filstar.csv"

RESULTS_FILE = "results_filstar.csv"
NOT_FOUND_FILE = "not_found_filstar.csv"

DEBUG_DIR = Path("debug_html")
DEBUG_DIR.mkdir(exist_ok=True)

# Пауза между заявките
REQUEST_DELAY = 2

# Максимално чакане при Cloudflare
CLOUDFLARE_TIMEOUT = 30


# ============================================================
# ЧЕТЕНЕ НА SKU CSV
# ============================================================

def load_skus():
    """
    Зарежда SKU от CSV.

    Игнорира:
    - празни редове
    - редове, започващи с #
    - всичко между ## и ##

    Пример:

    932562
    950594

    ##
    този ред се игнорира
    360468
    този също
    ##

    949513

    Резултат:
    932562
    950594
    949513
    """

    skus = []

    inside_comment = False

    with open(CSV_FILE, "r", encoding="utf-8-sig", newline="") as f:

        reader = csv.reader(f)

        for row in reader:

            if not row:
                continue

            # Събираме целия ред
            line = ",".join(row).strip()

            if not line:
                continue

            # ------------------------------------------------
            # COMMENT BLOCK ##
            # ------------------------------------------------

            if line.startswith("##"):
                inside_comment = not inside_comment
                continue

            if inside_comment:
                continue

            # ------------------------------------------------
            # Обикновен коментар
            # ------------------------------------------------

            if line.startswith("#"):
                continue

            # ------------------------------------------------
            # Ако CSV има header
            # ------------------------------------------------

            if line.lower() in (
                "sku",
                "код",
                "product sku",
                "sku,наличност",
                "sku,цена",
            ):
                continue

            # ------------------------------------------------
            # Вземаме първата стойност
            # ------------------------------------------------

            sku = row[0].strip()

            if not sku:
                continue

            # Премахваме кавички
            sku = sku.strip('"').strip("'")

            # Само цифри
            if not re.fullmatch(r"\d+", sku):
                continue

            skus.append(sku)

    # Премахване на дублирани SKU, като запазваме реда
    unique_skus = list(dict.fromkeys(skus))

    return unique_skus


# ============================================================
# DEBUG SAVE
# ============================================================

def save_debug(filename, content):

    path = DEBUG_DIR / filename

    try:
        path.write_text(content, encoding="utf-8")
    except Exception as e:
        print(f"⚠️ Debug save error: {e}")


# ============================================================
# CLOUDflare DETECTION
# ============================================================

def is_cloudflare(page):

    try:

        title = page.title().lower()

        content = page.content().lower()

        indicators = [
            "just a moment",
            "checking your browser",
            "enable javascript and cookies",
            "cf-chl",
            "challenge-platform",
            "cloudflare",
        ]

        for indicator in indicators:

            if indicator in title:
                return True

            if indicator in content:
                return True

        return False

    except Exception:
        return False


# ============================================================
# WAIT FOR CLOUDFLARE
# ============================================================

def wait_for_cloudflare(page):

    print("⏳ Проверка за Cloudflare...")

    start = time.time()

    while time.time() - start < CLOUDFLARE_TIMEOUT:

        if not is_cloudflare(page):

            print("✅ Cloudflare Challenge преминат")

            return True

        print("🛡️ Cloudflare Challenge...")

        time.sleep(3)

        try:
            page.reload(
                wait_until="domcontentloaded",
                timeout=30000
            )
        except Exception:
            pass

    print("❌ Cloudflare Challenge не беше преминат")

    return False


# ============================================================
# EXTRACT JSON OBJECTS
# ============================================================

def extract_json_objects(text):

    objects = []

    decoder = json.JSONDecoder()

    # Търсим всички места, от които може да започва JSON object
    for match in re.finditer(r"\{", text):

        start = match.start()

        try:

            obj, end = decoder.raw_decode(text[start:])

            if isinstance(obj, dict):

                objects.append(obj)

        except Exception:
            continue

    return objects


# ============================================================
# SEARCH -> PRODUCT ID
# ============================================================

def find_product_id(page, sku):

    search_url = f"{BASE_URL}/api/search?term={sku}"

    print(f"🌐 SEARCH: {search_url}")

    try:

        response = page.goto(
            search_url,
            wait_until="domcontentloaded",
            timeout=30000
        )

    except Exception as e:

        print(f"❌ Search error: {e}")

        return None

    if response is None:

        print("❌ Search няма response")

        return None

    status = response.status

    print(f"🔎 Search HTTP: {status}")

    try:
        content = page.content()
    except Exception:
        content = ""

    save_debug(
        f"search_{sku}.html",
        content
    )

    if status != 200:

        print(f"❌ Search HTTP: {status}")

        return None

    # --------------------------------------------------------
    # Първо опитваме JSON
    # --------------------------------------------------------

    try:

        body_text = page.locator("body").inner_text()

    except Exception:

        body_text = content

    json_objects = extract_json_objects(body_text)

    # --------------------------------------------------------
    # Търсим Product ID
    # --------------------------------------------------------

    candidates = []

    def recursive_find(obj):

        if isinstance(obj, dict):

            # Чести имена за ID
            for key in (
                "id",
                "productId",
                "product_id",
            ):

                if key in obj:

                    value = obj[key]

                    if isinstance(value, (int, str)):

                        value_str = str(value)

                        if value_str.isdigit():
                            candidates.append(value_str)

            for value in obj.values():
                recursive_find(value)

        elif isinstance(obj, list):

            for item in obj:
                recursive_find(item)

    for obj in json_objects:

        recursive_find(obj)

    # Премахваме дублирани ID
    candidates = list(dict.fromkeys(candidates))

    # --------------------------------------------------------
    # Ако JSON не е намерен, търсим в HTML
    # --------------------------------------------------------

    if not candidates:

        patterns = [

            # data-product-id="2967"
            r'data-product-id=["\'](\d+)["\']',

            # product-id="2967"
            r'product-id=["\'](\d+)["\']',

            # /get-serialize-product/2967
            r'/get-serialize-product/(\d+)',

            # productId: 2967
            r'productId["\']?\s*[:=]\s*["\']?(\d+)',

            # "id":2967
            r'["\']id["\']\s*:\s*["\']?(\d+)',
        ]

        for pattern in patterns:

            found = re.findall(
                pattern,
                content,
                flags=re.IGNORECASE
            )

            for value in found:

                if value not in candidates:
                    candidates.append(value)

    print(f"ID кандидати: {candidates}")

    # --------------------------------------------------------
    # ВАЖНО:
    # Search може да съдържа други ID-та.
    #
    # Затова проверяваме дали има URL към
    # get-serialize-product.
    # --------------------------------------------------------

    product_urls = re.findall(
        r'/get-serialize-product/(\d+)',
        content
    )

    product_urls = list(dict.fromkeys(product_urls))

    if product_urls:

        print(f"🔗 Product IDs от serialize URL: {product_urls}")

        # Ако има директен serialize ID,
        # използваме първия.
        return product_urls[0]

    # --------------------------------------------------------
    # Ако няма serialize URL,
    # използваме първия намерен ID
    # --------------------------------------------------------

    if candidates:

        return candidates[0]

    return None


# ============================================================
# PRODUCT DATA
# ============================================================

def get_product(page, product_id):

    product_url = (
        f"{BASE_URL}/get-serialize-product/{product_id}"
    )

    print(f"📦 PRODUCT: {product_url}")

    try:

        response = page.goto(
            product_url,
            wait_until="domcontentloaded",
            timeout=30000
        )

    except Exception as e:

        print(f"❌ Product navigation error: {e}")

        save_debug(
            f"product_{product_id}_error.html",
            page.content()
        )

        return None

    if response is None:

        print("❌ Product няма response")

        return None

    status = response.status

    print(f"📡 Product HTTP: {status}")

    # --------------------------------------------------------
    # Ако е Cloudflare
    # --------------------------------------------------------

    if status == 403 or is_cloudflare(page):

        if not wait_for_cloudflare(page):

            save_debug(
                f"product_{product_id}_error.html",
                page.content()
            )

            return None

        # След преминаване на Cloudflare
        try:

            response = page.goto(
                product_url,
                wait_until="domcontentloaded",
                timeout=30000
            )

            status = response.status if response else 0

        except Exception as e:

            print(f"❌ Product retry error: {e}")

            return None

        print(f"📡 Product retry HTTP: {status}")

    # --------------------------------------------------------
    # Ако все още е 403
    # --------------------------------------------------------

    if status == 403:

        print("❌ Product HTTP: 403")

        try:
            save_debug(
                f"product_{product_id}_error.html",
                page.content()
            )
        except Exception:
            pass

        return None

    # --------------------------------------------------------
    # Вземаме текста
    # --------------------------------------------------------

    try:

        text = page.locator("body").inner_text()

    except Exception:

        text = page.content()

    save_debug(
        f"product_{product_id}.html",
        text
    )

    # --------------------------------------------------------
    # Парсваме JSON
    # --------------------------------------------------------

    try:

        data = json.loads(text)

        if isinstance(data, dict):

            return data

    except Exception:
        pass

    # --------------------------------------------------------
    # Понякога JSON е embedded в HTML
    # --------------------------------------------------------

    json_objects = extract_json_objects(text)

    for obj in json_objects:

        if (
            isinstance(obj, dict)
            and (
                "variants" in obj
                or "stores" in obj
                or "name" in obj
            )
        ):

            return obj

    print("❌ Product data не е валиден JSON")

    return None


# ============================================================
# FIND VARIANT
# ============================================================

def find_variant(product, sku):

    variants = product.get("variants", [])

    if not isinstance(variants, list):
        return None

    for variant in variants:

        if not isinstance(variant, dict):
            continue

        variant_sku = str(
            variant.get("sku", "")
        ).strip()

        if variant_sku == str(sku):

            return variant

    return None


# ============================================================
# TOTAL QUANTITY
# ============================================================

def get_total_quantity(variant):

    """
    Връща общото количество от всички складове.

    Например:

    Пловдив = 1
    София   = 0

    Общо = 1

    НЕ връщаме складовете поотделно.
    """

    stores = variant.get("stores")

    if not stores:
        return 0

    total = 0

    if isinstance(stores, list):

        for store in stores:

            if not isinstance(store, dict):
                continue

            quantity = store.get("quantity", 0)

            try:
                total += int(quantity)
            except (ValueError, TypeError):
                pass

    return total


# ============================================================
# MAIN
# ============================================================

def main():

    skus = load_skus()

    print(f"Общо SKU: {len(skus)}")

    results = []
    not_found = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            locale="bg-BG",
            timezone_id="Europe/Sofia",
            viewport={
                "width": 1366,
                "height": 768
            },
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/131.0.0.0 "
                "Safari/537.36"
            )
        )

        page = context.new_page()

        # ----------------------------------------------------
        # Основни headers
        # ----------------------------------------------------

        page.set_extra_http_headers({
            "Accept-Language": "bg-BG,bg;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
        })

        # ----------------------------------------------------
        # Обработка на SKU
        # ----------------------------------------------------

        for sku in skus:

            print()
            print("================")
            print()
            print(f"➡️ SKU: {sku}")

            # ------------------------------------------------
            # SEARCH
            # ------------------------------------------------

            product_id = find_product_id(
                page,
                sku
            )

            if not product_id:

                print(
                    f"❌ Няма Product ID за SKU: {sku}"
                )

                not_found.append({
                    "SKU": sku,
                    "Причина": "Няма Product ID"
                })

                time.sleep(REQUEST_DELAY)

                continue

            print(
                f"✅ Product ID: {product_id}"
            )

            # ------------------------------------------------
            # PRODUCT
            # ------------------------------------------------

            product = get_product(
                page,
                product_id
            )

            if not product:

                print("❌ Няма product data")

                not_found.append({
                    "SKU": sku,
                    "Product ID": product_id,
                    "Причина": "Няма product data"
                })

                time.sleep(REQUEST_DELAY)

                continue

            # ------------------------------------------------
            # VARIANT
            # ------------------------------------------------

            variant = find_variant(
                product,
                sku
            )

            if not variant:

                print(
                    f"❌ Няма variant за SKU: {sku}"
                )

                not_found.append({
                    "SKU": sku,
                    "Product ID": product_id,
                    "Причина": "Няма variant"
                })

                time.sleep(REQUEST_DELAY)

                continue

            # ------------------------------------------------
            # PRODUCT DATA
            # ------------------------------------------------

            quantity = get_total_quantity(
                variant
            )

            price = variant.get(
                "discountedPrice"
            )

            if price is None:

                price = variant.get(
                    "price"
                )

            # ------------------------------------------------
            # РЕЗУЛТАТ
            # ------------------------------------------------

            print(f"📦 SKU: {sku}")
            print(f"📊 Общо количество: {quantity}")
            print(f"💰 Цена: {price}")

            results.append({
                "SKU": sku,
                "Product ID": product_id,
                "Наличност": quantity,
                "Цена": price
            })

            time.sleep(REQUEST_DELAY)

        browser.close()

    # ========================================================
    # SAVE RESULTS
    # ========================================================

    with open(
        RESULTS_FILE,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "SKU",
                "Product ID",
                "Наличност",
                "Цена"
            ]
        )

        writer.writeheader()

        writer.writerows(results)

    print()
    print(
        f"💾 Записани резултати: {RESULTS_FILE}"
    )

    # ========================================================
    # SAVE NOT FOUND
    # ========================================================

    with open(
        NOT_FOUND_FILE,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "SKU",
                "Product ID",
                "Причина"
            ]
        )

        writer.writeheader()

        writer.writerows(not_found)

    print(
        f"💾 Not found: {NOT_FOUND_FILE}"
    )

    print()
    print("✅ Готово")


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
