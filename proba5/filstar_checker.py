import csv
import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# ============================================================
# SETTINGS
# ============================================================

BASE_URL = "https://filstar.com"

CSV_FILE = Path("sku_list_filstar.csv")
DEBUG_DIR = Path("debug_html")

SEARCH_URL = BASE_URL + "/api/search?term={}"
PRODUCT_URL = BASE_URL + "/get-serialize-product/{}"

DEBUG_DIR.mkdir(exist_ok=True)

# Пауза между заявките
REQUEST_DELAY = 1.0

# Колко време Playwright да чака Cloudflare
CLOUDFLARE_TIMEOUT = 30000


# ============================================================
# HEADERS
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "bg-BG,bg;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": BASE_URL + "/",
    "Connection": "keep-alive",
}


# ============================================================
# LOAD SKU
# ============================================================

def load_skus(csv_file):
    """
    Зарежда SKU от CSV.

    ВАЖНО:
    Всичко между:
    
        ##
        ...
        ##

    се счита за коментар и НЕ се обработва.

    Също така се игнорират редове, започващи с #.
    """

    skus = []
    in_comment = False

    if not csv_file.exists():
        print(f"❌ Липсва файл: {csv_file}")
        return skus

    with open(
        csv_file,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        for raw_line in f:

            line = raw_line.strip()

            # ------------------------------------------------
            # Празен ред
            # ------------------------------------------------
            if not line:
                continue

            # ------------------------------------------------
            # ## започва / приключва блоков коментар
            # ------------------------------------------------
            if line.startswith("##"):
                in_comment = not in_comment
                continue

            # ------------------------------------------------
            # Всичко между ## ... ## се игнорира
            # ------------------------------------------------
            if in_comment:
                continue

            # ------------------------------------------------
            # Едноредов коментар
            # ------------------------------------------------
            if line.startswith("#"):
                continue

            # ------------------------------------------------
            # CSV header
            # ------------------------------------------------
            if line.lower().startswith("sku"):
                continue

            # ------------------------------------------------
            # Вземаме първата CSV колона
            # ------------------------------------------------
            try:
                row = next(
                    csv.reader([line])
                )
            except Exception:
                continue

            if not row:
                continue

            sku = row[0].strip()

            if not sku:
                continue

            # Само реални SKU стойности
            if not re.fullmatch(r"[A-Za-z0-9._-]+", sku):
                continue

            skus.append(sku)

    return skus


# ============================================================
# SAVE DEBUG
# ============================================================

def save_debug(filename, content):
    path = DEBUG_DIR / filename

    try:
        path.write_text(
            content,
            encoding="utf-8"
        )
        return path
    except Exception as e:
        print(f"⚠️ Debug write error: {e}")
        return None


# ============================================================
# CREATE REQUEST SESSION
# ============================================================

def create_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


# ============================================================
# SEARCH PRODUCT
# ============================================================

def search_product(session, sku):
    url = SEARCH_URL.format(sku)

    print(f"🌐 SEARCH: {url}")

    try:
        response = session.get(
            url,
            timeout=30
        )

        print(f"🔎 Search HTTP: {response.status_code}")

    except Exception as e:
        print(f"❌ Search error: {e}")
        return None

    debug_file = f"search_{sku}.html"
    save_debug(debug_file, response.text)

    print(f"🐞 Debug: {debug_file}")

    if response.status_code != 200:
        return None

    # --------------------------------------------------------
    # Опит за JSON
    # --------------------------------------------------------

    try:
        data = response.json()
    except Exception:

        # Понякога отговорът може да е HTML,
        # в който има JSON.
        data = None

    if data is None:

        text = response.text

        # Търсим числови product IDs
        ids = re.findall(
            r'"(?:id|productId|product_id)"\s*:\s*"?(\d+)"?',
            text,
            re.IGNORECASE
        )

        ids = list(dict.fromkeys(ids))

        print(f"ID кандидати: {ids}")

        if ids:
            return ids[0]

        return None

    # --------------------------------------------------------
    # Рекурсивно намиране на ID
    # --------------------------------------------------------

    candidates = []

    def find_ids(obj):

        if isinstance(obj, dict):

            for key, value in obj.items():

                key_lower = str(key).lower()

                if key_lower in (
                    "id",
                    "productid",
                    "product_id"
                ):

                    if isinstance(value, (int, str)):

                        value_str = str(value)

                        if value_str.isdigit():
                            candidates.append(value_str)

                find_ids(value)

        elif isinstance(obj, list):

            for item in obj:
                find_ids(item)

    find_ids(data)

    # Премахваме дублиранията
    candidates = list(dict.fromkeys(candidates))

    print(f"ID кандидати: {candidates}")

    if not candidates:
        return None

    return candidates[0]


# ============================================================
# CLOUDFLARE DETECTION
# ============================================================

def is_cloudflare_challenge(text):
    if not text:
        return False

    text_lower = text.lower()

    indicators = [
        "just a moment",
        "cf-chl",
        "challenge-platform",
        "cloudflare",
        "enable javascript and cookies to continue",
    ]

    return any(
        indicator in text_lower
        for indicator in indicators
    )


# ============================================================
# PLAYWRIGHT PRODUCT REQUEST
# ============================================================

def get_product_with_playwright(page, product_id):
    url = PRODUCT_URL.format(product_id)

    print(f"📦 PRODUCT: {url}")

    try:

        response = page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        if response is None:
            print("❌ Няма HTTP response")
            return None

        status = response.status

        print(f"📡 Product HTTP: {status}")

        # ----------------------------------------------------
        # Ако е 403 / Cloudflare
        # ----------------------------------------------------

        if status == 403:

            print("⏳ Проверка за Cloudflare...")

            try:

                page.wait_for_function(
                    """
                    () => {
                        const title = document.title.toLowerCase();
                        const body = document.body
                            ? document.body.innerText.toLowerCase()
                            : "";

                        return (
                            !title.includes("just a moment") &&
                            !body.includes("enable javascript and cookies to continue") &&
                            !document.querySelector("#challenge-running")
                        );
                    }
                    """,
                    timeout=CLOUDFLARE_TIMEOUT
                )

                print("✅ Cloudflare Challenge преминат")

            except PlaywrightTimeoutError:

                print("🛡️ Cloudflare Challenge не беше преминат")

                html = page.content()

                filename = (
                    f"product_{product_id}_error.html"
                )

                save_debug(
                    filename,
                    html
                )

                print(f"🐞 Debug: {filename}")

                return None

        # ----------------------------------------------------
        # Изчакваме съдържанието
        # ----------------------------------------------------

        try:
            page.wait_for_timeout(1500)
        except Exception:
            pass

        html = page.content()

        # ----------------------------------------------------
        # Ако все още е Cloudflare
        # ----------------------------------------------------

        if is_cloudflare_challenge(html):

            print("🛡️ Все още има Cloudflare Challenge")

            filename = (
                f"product_{product_id}_error.html"
            )

            save_debug(
                filename,
                html
            )

            print(f"🐞 Debug: {filename}")

            return None

        # ----------------------------------------------------
        # Debug при нормален отговор
        # ----------------------------------------------------

        if status != 200:

            filename = (
                f"product_{product_id}_error.html"
            )

            save_debug(
                filename,
                html
            )

            print(f"🐞 Debug: {filename}")

            return None

        return html

    except PlaywrightTimeoutError:

        print("❌ Playwright timeout")

        try:
            html = page.content()

            filename = (
                f"product_{product_id}_error.html"
            )

            save_debug(
                filename,
                html
            )

            print(f"🐞 Debug: {filename}")

        except Exception:
            pass

        return None

    except Exception as e:

        print(f"❌ Playwright error: {e}")

        return None


# ============================================================
# FIND PRODUCT JSON
# ============================================================

def extract_json_from_html(html):
    """
    Извлича JSON от get-serialize-product отговора.

    При нормален отговор обикновено самата страница
    съдържа JSON.
    """

    if not html:
        return None

    text = html.strip()

    # --------------------------------------------------------
    # 1. Директен JSON
    # --------------------------------------------------------

    try:
        return json.loads(text)
    except Exception:
        pass

    # --------------------------------------------------------
    # 2. HTML -> body text
    # --------------------------------------------------------

    try:

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        body_text = soup.get_text(
            strip=True
        )

        if body_text:

            try:
                return json.loads(body_text)
            except Exception:
                pass

    except Exception:
        pass

    # --------------------------------------------------------
    # 3. Търсим JSON object
    # --------------------------------------------------------

    match = re.search(
        r'(\{"id"\s*:.*\})',
        text,
        re.DOTALL
    )

    if match:

        candidate = match.group(1)

        try:
            return json.loads(candidate)
        except Exception:
            pass

    return None


# ============================================================
# CHECK SKU IN PRODUCT DATA
# ============================================================

def find_variant(product_data, sku):
    """
    Намира variant по SKU.
    """

    if not isinstance(product_data, dict):
        return None

    variants = product_data.get(
        "variants",
        []
    )

    if not isinstance(variants, list):
        return None

    for variant in variants:

        if not isinstance(variant, dict):
            continue

        variant_sku = str(
            variant.get("sku", "")
        ).strip()

        if variant_sku == str(sku).strip():
            return variant

    return None


# ============================================================
# GET TOTAL QUANTITY
# ============================================================

def get_total_quantity(variant):
    """
    Взема ОБЩОТО количество.

    Не използваме отделно София / Пловдив.

    Приоритет:
        1. quantity
        2. сумата от stores
    """

    if not isinstance(variant, dict):
        return 0

    # --------------------------------------------------------
    # Най-надеждно: quantity
    # --------------------------------------------------------

    quantity = variant.get("quantity")

    if isinstance(quantity, (int, float)):
        return int(quantity)

    # --------------------------------------------------------
    # Ако quantity липсва - сумираме складовете
    # --------------------------------------------------------

    stores = variant.get(
        "stores",
        []
    )

    total = 0

    if isinstance(stores, list):

        for store in stores:

            if not isinstance(store, dict):
                continue

            q = store.get("quantity", 0)

            try:
                total += int(q)
            except Exception:
                pass

    return total


# ============================================================
# PROCESS PRODUCT
# ============================================================

def process_product(
    page,
    sku,
    product_id
):

    html = get_product_with_playwright(
        page,
        product_id
    )

    if not html:

        print("❌ Няма product data")
        return None

    product_data = extract_json_from_html(
        html
    )

    if not product_data:

        filename = (
            f"product_{product_id}_parse_error.html"
        )

        save_debug(
            filename,
            html
        )

        print(
            f"❌ Не успях да извлека JSON: {filename}"
        )

        return None

    # --------------------------------------------------------
    # Variant
    # --------------------------------------------------------

    variant = find_variant(
        product_data,
        sku
    )

    if not variant:

        print(
            f"❌ Няма variant за SKU: {sku}"
        )

        return None

    # --------------------------------------------------------
    # Quantity
    # --------------------------------------------------------

    total_quantity = get_total_quantity(
        variant
    )

    # --------------------------------------------------------
    # Price
    # --------------------------------------------------------

    price = variant.get(
        "discountedPrice"
    )

    if price is None:
        price = variant.get(
            "price"
        )

    try:
        price = float(price)
    except Exception:
        price = 0.0

    # --------------------------------------------------------
    # Name
    # --------------------------------------------------------

    name = product_data.get(
        "name",
        ""
    )

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    result = {
        "SKU": str(sku),
        "Наличност": (
            "Да"
            if total_quantity > 0
            else "Не"
        ),
        "Цена": price,
        "Бройки": total_quantity,
        "Product ID": product_data.get(
            "id",
            product_id
        ),
        "Име": name,
    }

    print(
        f"📊 SKU: {sku} | "
        f"Общо количество: {total_quantity} | "
        f"Цена: {price:.2f}"
    )

    return result


# ============================================================
# SAVE RESULTS CSV
# ============================================================

def save_results(results):

    output_file = Path(
        "results_filstar.csv"
    )

    fieldnames = [
        "SKU",
        "Наличност",
        "Цена",
        "Бройки",
        "Product ID",
        "Име",
    ]

    with open(
        output_file,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writeheader()

        for result in results:

            writer.writerow(result)

    print(
        f"💾 Записани резултати: {output_file}"
    )


# ============================================================
# SAVE NOT FOUND
# ============================================================

def save_not_found(skus):

    output_file = Path(
        "not_found_filstar.csv"
    )

    with open(
        output_file,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.writer(f)

        writer.writerow([
            "SKU"
        ])

        for sku in skus:
            writer.writerow([
                sku
            ])

    print(
        f"💾 Not found: {output_file}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # Зареждане на SKU
    # --------------------------------------------------------

    skus = load_skus(
        CSV_FILE
    )

    print()
    print(
        f"Общо SKU: {len(skus)}"
    )
    print()

    if not skus:

        print(
            "⚠️ Няма SKU за обработка."
        )

        save_results([])

        return

    session = create_session()

    results = []
    not_found = []

    # --------------------------------------------------------
    # Playwright
    # --------------------------------------------------------

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
        )

        context = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            locale="bg-BG",
            viewport={
                "width": 1920,
                "height": 1080
            },
            extra_http_headers={
                "Accept-Language": HEADERS[
                    "Accept-Language"
                ]
            }
        )

        page = context.new_page()

        # ----------------------------------------------------
        # Обработка на SKU
        # ----------------------------------------------------

        for sku in skus:

            print()
            print(
                "================"
            )
            print()
            print(
                f"➡️ SKU: {sku}"
            )
            print()

            # ------------------------------------------------
            # Search
            # ------------------------------------------------

            product_id = search_product(
                session,
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

            # ------------------------------------------------
            # Product
            # ------------------------------------------------

            result = process_product(
                page,
                sku,
                product_id
            )

            if result:

                results.append(
                    result
                )

            else:

                not_found.append(
                    sku
                )

            # ------------------------------------------------
            # Пауза
            # ------------------------------------------------

            time.sleep(
                REQUEST_DELAY
            )

        # ----------------------------------------------------
        # Close
        # ----------------------------------------------------

        context.close()
        browser.close()

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    save_results(
        results
    )

    save_not_found(
        not_found
    )

    print()
    print(
        "✅ Готово"
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
