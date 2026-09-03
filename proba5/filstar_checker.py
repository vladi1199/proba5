import csv
import re
import time
from pathlib import Path

from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)


BASE_URL = "https://filstar.com"

INPUT_FILE = "sku_list_filstar.csv"
OUTPUT_FILE = "results_filstar.csv"
NOT_FOUND_FILE = "not_found_filstar.csv"

# За теста няма изкуствено забавяне.
WAIT = 0


# ============================================================
# ЧЕТЕНЕ НА SKU
#
# Всичко между две линии ## се игнорира.
#
# Пример:
#
# SKU
# 946537
# 946534
# ##
# 946535
# 946536
# ##
# 951786
#
# Ще бъдат обработени:
# 946537
# 946534
# 951786
# ============================================================

def read_skus():

    skus = []
    in_comment_block = False

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        reader = csv.reader(f)

        for row in reader:

            if not row:
                continue

            first = str(row[0]).strip()

            if not first:
                continue

            # ------------------------------------------------
            # ## = начало/край на коментарен блок
            # ------------------------------------------------

            if first == "##":

                in_comment_block = not in_comment_block
                continue

            # ------------------------------------------------
            # Игнорираме всичко между ##
            # ------------------------------------------------

            if in_comment_block:
                continue

            # ------------------------------------------------
            # Header
            # ------------------------------------------------

            if first.lower() == "sku":
                continue

            sku = first.strip()

            if sku:
                skus.append(sku)

    return skus


# ============================================================
# FIND PRODUCT ID
#
# /api/search?term=SKU
#
# Използваме го само за намиране на parent product ID.
#
# Пример:
#
# 946537 -> 2557
# ============================================================

def find_product_id(page, sku):

    url = (
        f"{BASE_URL}/api/search"
        f"?term={sku}"
    )

    try:

        response = page.request.get(
            url,
            timeout=30000
        )

        print(
            f"   /api/search -> HTTP "
            f"{response.status}"
        )

        if response.status != 200:
            return None

        # ВАЖНО:
        # Playwright използва response.text()
        html = response.text()

        matches = re.findall(
            r'data-product-id=["\'](\d+)["\']',
            html,
            re.IGNORECASE
        )

        if not matches:
            return None

        # Премахваме дубликатите,
        # като запазваме реда.
        unique_ids = list(
            dict.fromkeys(matches)
        )

        # Първо проверяваме product card,
        # в който присъства конкретният SKU.
        for product_id in unique_ids:

            pattern = (
                rf'data-product-id=["\']'
                rf'{re.escape(product_id)}'
                rf'["\']'
            )

            match = re.search(
                pattern,
                html,
                re.IGNORECASE
            )

            if not match:
                continue

            start = max(
                0,
                match.start() - 500
            )

            end = min(
                len(html),
                match.end() + 6000
            )

            context = html[start:end]

            if sku in context:
                return product_id

        # При текущия /api/search първият ID
        # е parent product-а.
        return unique_ids[0]

    except Exception as e:

        print(
            f"   ❌ Грешка при /api/search: {e}"
        )

        return None


# ============================================================
# FIND PRODUCT URL
#
# От /api/search взимаме реалния URL на продукта.
#
# Например:
#
# https://filstar.com/Muhi-za-buldo-bz
# ============================================================

def find_product_url(page, sku):

    url = (
        f"{BASE_URL}/api/search"
        f"?term={sku}"
    )

    try:

        response = page.request.get(
            url,
            timeout=30000
        )

        if response.status != 200:
            return None

        # ВАЖНО:
        # response.text е method,
        # затова трябва response.text()
        html = response.text()

        hrefs = re.findall(
            r'href=["\']([^"\']+)["\']',
            html,
            re.IGNORECASE
        )

        for href in hrefs:

            href = href.strip()

            if not href:
                continue

            if href.startswith("/"):
                full_url = (
                    BASE_URL + href
                )

            elif href.startswith(
                "http://"
            ) or href.startswith(
                "https://"
            ):
                full_url = href

            else:
                continue

            # ------------------------------------------------
            # Игнорираме технически URL-и.
            # ------------------------------------------------

            if (
                "/search" in full_url
                or "/cart" in full_url
                or "/login" in full_url
                or "/register" in full_url
                or "/account" in full_url
            ):
                continue

            return full_url

        return None

    except Exception as e:

        print(
            f"   ❌ Грешка при URL: {e}"
        )

        return None


# ============================================================
# EXTRACT VUE PRODUCT.VARIANTS
#
# Това е ключовата част.
#
# От Console установихме:
#
# const v = document.querySelectorAll("*")[544].__vue__;
#
# v.product
# v.product.variants
#
# Тук намираме същия Vue компонент автоматично,
# без да разчитаме на element[544].
# ============================================================

def extract_variants_from_vue(page):

    return page.evaluate(
        """
        () => {

            const elements =
                document.querySelectorAll("*");

            for (const el of elements) {

                const vue = el.__vue__;

                if (!vue) {
                    continue;
                }

                if (
                    vue.product &&
                    Array.isArray(
                        vue.product.variants
                    )
                ) {

                    return vue.product.variants.map(
                        v => ({

                            id:
                                v.id ?? null,

                            sku:
                                v.sku ?? null,

                            quantity:
                                v.quantity ?? 0,

                            price:
                                v.price ?? null,

                            discountedPrice:
                                v.discountedPrice ?? null,

                            discountedRetailPrice:
                                v.discountedRetailPrice ?? null,

                            barcode:
                                v.barcode ?? null,

                            stores:
                                Array.isArray(v.stores)
                                    ? v.stores.map(
                                        s => ({
                                            id:
                                                s.id ?? null,

                                            name:
                                                s.name ?? null,

                                            quantity:
                                                s.quantity ?? 0
                                        })
                                    )
                                    : []
                        })
                    );
                }
            }

            return null;
        }
        """
    )


# ============================================================
# WAIT FOR VUE
#
# Vue betöltése след XHR-а може да отнеме малко време.
# Проверяваме през 500 ms.
# ============================================================

def wait_for_vue_variants(page):

    for attempt in range(20):

        variants = (
            extract_variants_from_vue(
                page
            )
        )

        if variants:

            return variants

        page.wait_for_timeout(500)

    return None


# ============================================================
# FIND VARIANT BY SKU
#
# Това е еквивалентът на Vue:
#
# this.variants.filter(
#     t => t.sku === u
# )[0]
# ============================================================

def find_variant(
    variants,
    sku
):

    sku = str(
        sku
    ).strip()

    for variant in variants:

        variant_sku = str(
            variant.get(
                "sku",
                ""
            )
        ).strip()

        if variant_sku == sku:

            return variant

    return None


# ============================================================
# PRICE
#
# Използваме normal price.
#
# При твоя пример:
#
# price = 1.99
# discountedPrice = 1.99
# discountedRetailPrice = 1.99
#
# Получаваме:
#
# 1.99
# ============================================================

def get_price(variant):

    value = variant.get(
        "price"
    )

    if value is None:

        value = variant.get(
            "discountedPrice"
        )

    if value is None:

        value = variant.get(
            "discountedRetailPrice"
        )

    if value is None:
        return ""

    try:

        return f"{float(value):.2f}"

    except Exception:

        return str(value)


# ============================================================
# QUANTITY
# ============================================================

def get_quantity(variant):

    value = variant.get(
        "quantity",
        0
    )

    try:

        return int(value)

    except Exception:

        try:

            return int(
                float(value)
            )

        except Exception:

            return 0


# ============================================================
# STORE QUANTITY
#
# variant.stores
# ============================================================

def get_store_quantity(
    variant,
    wanted_store
):

    stores = variant.get(
        "stores",
        []
    )

    if not isinstance(
        stores,
        list
    ):
        return ""

    for store in stores:

        if not isinstance(
            store,
            dict
        ):
            continue

        name = str(
            store.get(
                "name",
                ""
            )
        ).strip()

        if (
            name.lower()
            == wanted_store.lower()
        ):

            value = store.get(
                "quantity",
                0
            )

            try:

                return int(value)

            except Exception:

                return 0

    return ""


# ============================================================
# BUILD RESULT
# ============================================================

def build_result(
    sku,
    product_id,
    variant
):

    quantity = get_quantity(
        variant
    )

    price = get_price(
        variant
    )

    barcode = str(
        variant.get(
            "barcode",
            ""
        )
    ).strip()

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

    return {

        "SKU":
            sku,

        "Наличност":
            availability,

        "Бройки":
            quantity,

        "Цена":
            price,

        "Product ID":
            product_id,

        "Variant ID":
            variant.get(
                "id",
                ""
            ),

        "Barcode":
            barcode,

        "Пловдив":
            plovdiv,

        "София":
            sofia,
    }


# ============================================================
# SAVE RESULTS
# ============================================================

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

        writer.writerows(
            results
        )


# ============================================================
# SAVE NOT FOUND
# ============================================================

def save_not_found(
    not_found
):

    with open(
        NOT_FOUND_FILE,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.writer(f)

        writer.writerow(
            ["SKU"]
        )

        for sku in not_found:

            writer.writerow(
                [sku]
            )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print(" FILSTAR CHECKER")
    print(" BROWSER + VUE product.variants")
    print("=" * 70)
    print()

    skus = read_skus()

    print(
        f"🧾 SKU за проверка: "
        f"{len(skus)}"
    )

    print()

    if not skus:

        print(
            "❌ Няма SKU за обработка."
        )

        return

    results = []
    not_found = []

    # --------------------------------------------------------
    # product_id -> variants
    #
    # Един продукт може да съдържа много SKU.
    # Зареждаме страницата само веднъж.
    # --------------------------------------------------------

    product_cache = {}

    with sync_playwright() as p:

        print(
            "🌐 Стартирам Chromium..."
        )

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
                "Mozilla/5.0 "
                "(Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/131.0.0.0 "
                "Safari/537.36"
            )
        )

        page = context.new_page()

        # ====================================================
        # SKU LOOP
        # ====================================================

        for index, sku in enumerate(
            skus,
            start=1
        ):

            print(
                f"[{index}/{len(skus)}] "
                f"🔎 {sku}"
            )

            # =================================================
            # 1. PRODUCT ID
            # =================================================

            product_id = find_product_id(
                page,
                sku
            )

            if not product_id:

                print(
                    "   ❌ Product ID "
                    "не е намерен."
                )

                not_found.append(
                    sku
                )

                continue

            print(
                f"   📦 Product ID: "
                f"{product_id}"
            )

            # =================================================
            # 2. CACHE
            # =================================================

            if product_id in product_cache:

                variants = product_cache[
                    product_id
                ]

                print(
                    f"   ♻️ Cache → "
                    f"{len(variants)} variants"
                )

            else:

                # =============================================
                # 3. PRODUCT URL
                # =============================================

                product_url = find_product_url(
                    page,
                    sku
                )

                if not product_url:

                    print(
                        "   ❌ Product URL "
                        "не е намерен."
                    )

                    not_found.append(
                        sku
                    )

                    continue

                print(
                    f"   🌐 {product_url}"
                )

                # =============================================
                # 4. ОТВАРЯМЕ ПРОДУКТА
                # =============================================

                try:

                    page.goto(
                        product_url,
                        wait_until="domcontentloaded",
                        timeout=60000
                    )

                except PlaywrightTimeoutError:

                    print(
                        "   ⚠️ Page timeout. "
                        "Проверявам Vue..."
                    )

                # =============================================
                # 5. VUE
                # =============================================

                print(
                    "   ⏳ Чакам "
                    "product.variants..."
                )

                variants = (
                    wait_for_vue_variants(
                        page
                    )
                )

                # =============================================
                # 6. VUE НЕ Е НАМЕРЕН
                # =============================================

                if not variants:

                    print(
                        "   ❌ "
                        "product.variants "
                        "не е намерен."
                    )

                    # Debug само при грешка.
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

                    not_found.append(
                        sku
                    )

                    continue

                # =============================================
                # 7. CACHE
                # =============================================

                product_cache[
                    product_id
                ] = variants

                print(
                    f"   🔢 Vue variants: "
                    f"{len(variants)}"
                )

            # =================================================
            # 8. FIND SKU
            # =================================================

            variant = find_variant(
                variants,
                sku
            )

            if not variant:

                print(
                    "   ❌ SKU не е намерен "
                    "в product.variants."
                )

                not_found.append(
                    sku
                )

                continue

            # =================================================
            # 9. RESULT
            # =================================================

            result = build_result(
                sku,
                product_id,
                variant
            )

            results.append(
                result
            )

            print(
                f"   ✅ Variant ID: "
                f"{result['Variant ID']}"
            )

            print(
                f"   📦 Бройки: "
                f"{result['Бройки']}"
            )

            print(
                f"   💰 Цена: "
                f"{result['Цена']}"
            )

            print(
                f"   🏬 Пловдив: "
                f"{result['Пловдив']}"
            )

            print(
                f"   🏬 София: "
                f"{result['София']}"
            )

            print()

            if WAIT > 0:

                time.sleep(
                    WAIT
                )

        # ====================================================
        # CLOSE BROWSER
        # ====================================================

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

    print()
    print("=" * 70)
    print(" ГОТОВО")
    print("=" * 70)
    print()

    print(
        f"✅ Успешни: "
        f"{len(results)}"
    )

    print(
        f"❌ Ненамерени: "
        f"{len(not_found)}"
    )

    print(
        f"📦 Заредени продукти: "
        f"{len(product_cache)}"
    )

    print()

    print(
        f"📄 Резултати: "
        f"{OUTPUT_FILE}"
    )

    print(
        f"📄 Ненамерени: "
        f"{NOT_FOUND_FILE}"
    )

    print()


if __name__ == "__main__":
    main()
