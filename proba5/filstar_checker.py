import csv
import json
import time
import re
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


BASE_URL = "https://filstar.com"

INPUT_FILE = "sku_list_filstar.csv"
OUTPUT_FILE = "results_filstar.csv"
NOT_FOUND_FILE = "not_found_filstar.csv"

WAIT = 2


def read_skus():
    skus = []

    with open(INPUT_FILE, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        sku_column = None

        for column in reader.fieldnames or []:
            if column.strip().lower() == "sku":
                sku_column = column
                break

        if not sku_column:
            raise RuntimeError("Няма колона SKU в CSV файла.")

        for row in reader:
            sku = str(row.get(sku_column, "")).strip()

            if sku:
                skus.append(sku)

    return skus


def find_product_id(page, sku):
    """
    Използваме вече доказания /api/search.
    От него ни трябва само parent product ID.
    """

    url = f"{BASE_URL}/api/search?term={sku}"

    try:
        response = page.request.get(url, timeout=30000)

        if response.status != 200:
            print(f"   ❌ /api/search HTTP {response.status}")
            return None

        html = response.text()

        # data-product-id="2557"
        pattern = (
            r'data-product-id=["\'](\d+)["\']'
        )

        ids = re.findall(pattern, html)

        if not ids:
            return None

        # Запазваме първия product ID.
        return ids[0]

    except Exception as e:
        print(f"   ❌ Грешка при /api/search: {e}")
        return None


def extract_variants_from_vue(page):
    """
    Това е ключовата част.

    В браузъра намираме Vue компонента, който вече установихме
    от Console, и взимаме:

        __vue__.product.variants

    Не правим нов API parser.
    Не измисляме структура.
    Използваме реалния Vue state.
    """

    result = page.evaluate("""
    () => {

        const elements = document.querySelectorAll("*");

        for (const el of elements) {

            const vue = el.__vue__;

            if (!vue) {
                continue;
            }

            // Това е компонентът, който намерихме
            // при диагностиката.
            if (
                vue.product &&
                Array.isArray(vue.product.variants)
            ) {

                return vue.product.variants.map(v => ({
                    id: v.id ?? null,
                    sku: v.sku ?? null,
                    quantity: v.quantity ?? 0,
                    price: v.price ?? null,
                    discountedPrice: v.discountedPrice ?? null,
                    discountedRetailPrice:
                        v.discountedRetailPrice ?? null,
                    barcode: v.barcode ?? null,
                    stores: Array.isArray(v.stores)
                        ? v.stores.map(s => ({
                            id: s.id ?? null,
                            name: s.name ?? null,
                            quantity: s.quantity ?? 0
                        }))
                        : []
                }));
            }
        }

        return null;
    }
    """)

    return result


def load_product_and_variants(page, product_id):
    """
    Зареждаме реалната продуктова страница.

    Vue на страницата сам извиква:
        /get-serialize-product/{product_id}

    След като Vue приключи, четем:
        __vue__.product.variants
    """

    url = f"{BASE_URL}/get-product/{product_id}"

    # Не разчитаме на URL-а да е точно този.
    # Първо отваряме продуктовата страница през API HTML-а,
    # като взимаме реалния href.
    return None


def find_product_url(page, product_id, sku):
    """
    Намираме реалния URL на продукта от /api/search.
    """

    url = f"{BASE_URL}/api/search?term={sku}"

    try:
        response = page.request.get(url, timeout=30000)

        if response.status != 200:
            return None

        html = response.text()

        # Намираме всички href към продуктови страници.
        matches = re.findall(
            r'href=["\']([^"\']+)["\']',
            html
        )

        for href in matches:

            if href.startswith("/"):
                full = BASE_URL + href
            elif href.startswith("http"):
                full = href
            else:
                continue

            # Изключваме технически URL-и.
            if (
                "/search" in full
                or "/cart" in full
                or "/login" in full
                or "/register" in full
            ):
                continue

            return full

        return None

    except Exception as e:
        print(f"   ❌ Грешка при намиране на URL: {e}")
        return None


def get_variant(variants, sku):

    sku = str(sku).strip()

    for variant in variants:

        if str(variant.get("sku", "")).strip() == sku:
            return variant

    return None


def get_price(variant):

    value = variant.get("price")

    if value is None:
        value = variant.get("discountedPrice")

    if value is None:
        value = variant.get("discountedRetailPrice")

    if value is None:
        return ""

    try:
        return f"{float(value):.2f}"
    except Exception:
        return str(value)


def get_store_quantity(variant, store_name):

    for store in variant.get("stores", []):

        name = str(
            store.get("name", "")
        ).strip()

        if name.lower() == store_name.lower():

            try:
                return int(
                    store.get("quantity", 0)
                )
            except Exception:
                return 0

    return ""


def save_results(results):

    fields = [
        "SKU",
        "Наличност",
        "Бройки",
        "Цена",
        "Product ID",
        "Variant ID",
        "Barcode",
        "Пловдив",
        "София",
    ]

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields
        )

        writer.writeheader()
        writer.writerows(results)


def save_not_found(items):

    with open(
        NOT_FOUND_FILE,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.writer(f)
        writer.writerow(["SKU"])

        for sku in items:
            writer.writerow([sku])


def main():

    print()
    print("=" * 60)
    print(" FILSTAR CHECKER - BROWSER/VUE")
    print("=" * 60)
    print()

    skus = read_skus()

    print(f"🧾 Общо SKU: {len(skus)}")
    print()

    results = []
    not_found = []

    # Cache на product variants.
    #
    # Един product може да има 6, 10, 20 и т.н. SKU.
    # Зареждаме Vue само веднъж за всеки product.
    product_cache = {}

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            viewport={
                "width": 1440,
                "height": 1000
            },
            locale="bg-BG",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )
        )

        page = context.new_page()

        for index, sku in enumerate(
            skus,
            start=1
        ):

            print(
                f"[{index}/{len(skus)}] "
                f"SKU: {sku}"
            )

            # ------------------------------------------------
            # 1. Product ID
            # ------------------------------------------------

            product_id = find_product_id(
                page,
                sku
            )

            if not product_id:

                print(
                    "   ❌ Product ID не е намерен."
                )

                not_found.append(sku)

                time.sleep(WAIT)
                continue

            print(
                f"   📦 Product ID: {product_id}"
            )

            # ------------------------------------------------
            # 2. Ако product вече е зареден,
            #    използваме кеша.
            # ------------------------------------------------

            if product_id in product_cache:

                variants = product_cache[
                    product_id
                ]

                print(
                    f"   ♻️ Cache: "
                    f"{len(variants)} variants"
                )

            else:

                # ------------------------------------------------
                # Намираме реалния URL на продукта.
                # ------------------------------------------------

                product_url = find_product_url(
                    page,
                    product_id,
                    sku
                )

                if not product_url:

                    print(
                        "   ❌ Product URL не е намерен."
                    )

                    not_found.append(sku)

                    time.sleep(WAIT)
                    continue

                print(
                    f"   🌐 {product_url}"
                )

                # ------------------------------------------------
                # Зареждаме страницата през Chromium.
                # ------------------------------------------------

                try:

                    page.goto(
                        product_url,
                        wait_until="domcontentloaded",
                        timeout=60000
                    )

                    # Vue трябва да има време да изпълни
                    # AddToCart.js и да зареди product.
                    page.wait_for_timeout(3000)

                except PlaywrightTimeoutError:

                    print(
                        "   ⚠️ Page timeout - проверявам "
                        "дали Vue все пак е зареден."
                    )

                # ------------------------------------------------
                # Изчакваме product.variants.
                # ------------------------------------------------

                variants = None

                for attempt in range(15):

                    variants = extract_variants_from_vue(
                        page
                    )

                    if variants:

                        break

                    page.wait_for_timeout(1000)

                if not variants:

                    print(
                        "   ❌ Vue product.variants "
                        "не беше намерен."
                    )

                    # Запазваме HTML за диагностика,
                    # само ако не е успяло.
                    try:

                        debug_dir = Path(
                            "debug_html"
                        )

                        debug_dir.mkdir(
                            exist_ok=True
                        )

                        page.screenshot(
                            path=str(
                                debug_dir /
                                f"failed_{sku}.png"
                            ),
                            full_page=True
                        )

                        with open(
                            debug_dir /
                            f"failed_{sku}.html",
                            "w",
                            encoding="utf-8"
                        ) as f:

                            f.write(
                                page.content()
                            )

                    except Exception:
                        pass

                    not_found.append(sku)

                    time.sleep(WAIT)
                    continue

                product_cache[
                    product_id
                ] = variants

                print(
                    f"   🔢 Vue variants: "
                    f"{len(variants)}"
                )

            # ------------------------------------------------
            # 3. Намираме конкретния SKU
            # ------------------------------------------------

            variant = get_variant(
                variants,
                sku
            )

            if not variant:

                print(
                    "   ❌ SKU не е намерен "
                    "в product.variants."
                )

                not_found.append(sku)

                time.sleep(WAIT)
                continue

            # ------------------------------------------------
            # 4. Реалните данни от Vue
            # ------------------------------------------------

            try:
                quantity = int(
                    variant.get(
                        "quantity",
                        0
                    )
                )
            except Exception:
                quantity = 0

            price = get_price(
                variant
            )

            barcode = variant.get(
                "barcode",
                ""
            )

            plovdiv = get_store_quantity(
                variant,
                "Пловдив"
            )

            sofia = get_store_quantity(
                variant,
                "София"
            )

            availability = (
                "Наличен"
                if quantity > 0
                else "Изчерпан"
            )

            result = {
                "SKU": sku,
                "Наличност": availability,
                "Бройки": quantity,
                "Цена": price,
                "Product ID": product_id,
                "Variant ID": variant.get(
                    "id",
                    ""
                ),
                "Barcode": barcode,
                "Пловдив": plovdiv,
                "София": sofia,
            }

            results.append(result)

            print(
                f"   ✅ Variant ID: {result['Variant ID']}"
            )

            print(
                f"   📦 Бройки: {quantity}"
            )

            print(
                f"   💰 Цена: {price}"
            )

            print(
                f"   🏬 Пловдив: {plovdiv}"
            )

            print(
                f"   🏬 София: {sofia}"
            )

            print()

            time.sleep(WAIT)

        browser.close()

    save_results(results)
    save_not_found(not_found)

    print()
    print("=" * 60)
    print(" ГОТОВО")
    print("=" * 60)
    print()
    print(f"✅ Успешни: {len(results)}")
    print(f"❌ Ненамерени: {len(not_found)}")
    print()
    print(f"📄 {OUTPUT_FILE}")
    print(f"📄 {NOT_FOUND_FILE}")
    print()


if __name__ == "__main__":
    main()
