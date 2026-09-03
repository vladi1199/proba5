import csv
import re
import time
from pathlib import Path

from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)


# ============================================================
# SETTINGS
# ============================================================

BASE_URL = "https://filstar.com"

INPUT_FILE = "sku_list_filstar.csv"
OUTPUT_FILE = "results_filstar.csv"
NOT_FOUND_FILE = "not_found_filstar.csv"

# 0 = без изкуствено чакане между SKU
WAIT = 0


# ============================================================
# READ SKU LIST
#
# Всичко между:
#
# ##
# ...
# ##
#
# се пропуска.
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

            # -----------------------------------------------
            # ## = начало / край на коментарен блок
            # -----------------------------------------------

            if first == "##":

                in_comment_block = not in_comment_block

                continue

            # -----------------------------------------------
            # Всичко между ## и ## се пропуска
            # -----------------------------------------------

            if in_comment_block:
                continue

            # -----------------------------------------------
            # Header
            # -----------------------------------------------

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
# Например:
#
# 946537 -> 2557
# ============================================================

def find_product_id(page, sku):

    url = f"{BASE_URL}/api/search?term={sku}"

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

        html = response.text()

        # ----------------------------------------------------
        # Намираме всички product IDs
        # ----------------------------------------------------

        matches = re.findall(
            r'data-product-id=["\'](\d+)["\']',
            html,
            re.IGNORECASE
        )

        if not matches:
            return None

        # Премахваме дубликатите
        unique_ids = list(
            dict.fromkeys(matches)
        )

        # ----------------------------------------------------
        # Търсим product card, в който присъства SKU
        # ----------------------------------------------------

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
                match.start() - 5000
            )

            end = min(
                len(html),
                match.end() + 10000
            )

            product_html = html[
                start:end
            ]

            if sku in product_html:

                return product_id

        # ----------------------------------------------------
        # Fallback
        # ----------------------------------------------------

        return unique_ids[0]

    except Exception as e:

        print(
            f"   ❌ Грешка при /api/search: "
            f"{e}"
        )

        return None


# ============================================================
# FIND PRODUCT URL
#
# ВАЖНО:
#
# Не взимаме първия href от HTML-а.
#
# Първият href може да бъде:
#
# https://a.omappapi.com
#
# Вместо това намираме конкретния product card
# по data-product-id.
# ============================================================

def find_product_url(
    page,
    sku,
    product_id
):

    url = f"{BASE_URL}/api/search?term={sku}"

    try:

        response = page.request.get(
            url,
            timeout=30000
        )

        if response.status != 200:
            return None

        html = response.text()

        # ----------------------------------------------------
        # Намираме конкретния Product ID
        # ----------------------------------------------------

        product_pattern = (
            rf'data-product-id=["\']'
            rf'{re.escape(str(product_id))}'
            rf'["\']'
        )

        match = re.search(
            product_pattern,
            html,
            re.IGNORECASE
        )

        if not match:
            return None

        # ----------------------------------------------------
        # Взимаме голям контекст около product card-а
        # ----------------------------------------------------

        start = max(
            0,
            match.start() - 10000
        )

        end = min(
            len(html),
            match.end() + 20000
        )

        product_html = html[
            start:end
        ]

        # ----------------------------------------------------
        # Намираме href-овете
        # ----------------------------------------------------

        hrefs = re.findall(
            r'href=["\']([^"\']+)["\']',
            product_html,
            re.IGNORECASE
        )

        for href in hrefs:

            href = href.strip()

            if not href:
                continue

            # ------------------------------------------------
            # Външни домейни НЕ ни интересуват
            # ------------------------------------------------

            if (
                href.startswith("http://")
                or
                href.startswith("https://")
            ):

                if not href.startswith(
                    BASE_URL
                ):
                    continue

                full_url = href

            elif href.startswith("/"):

                full_url = (
                    BASE_URL + href
                )

            else:

                continue

            lower_url = full_url.lower()

            # ------------------------------------------------
            # Изключваме технически URL-и
            # ------------------------------------------------

            forbidden_parts = [

                "/search",
                "/cart",
                "/login",
                "/register",
                "/account",
                "/api/",
                ".js",
                ".css",
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
                ".svg",
                ".gif",
                "omappapi",
            ]

            if any(
                part in lower_url
                for part in forbidden_parts
            ):
                continue

            # ------------------------------------------------
            # Само filstar.com
            # ------------------------------------------------

            if not full_url.startswith(
                BASE_URL + "/"
            ):
                continue

            return full_url

        return None

    except Exception as e:

        print(
            f"   ❌ Грешка при URL: "
            f"{e}"
        )

        return None


# ============================================================
# EXTRACT VUE PRODUCT.VARIANTS
#
# Търсим автоматично Vue компонента, който съдържа:
#
# vue.product.variants
#
# Не разчитаме на конкретен element[544].
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
# ============================================================

def wait_for_vue_variants(page):

    # Проверяваме до 10 секунди
    # на интервали от 500 ms.

    for attempt in range(20):

        variants = (
            extract_variants_from_vue(
                page
            )
        )

        if variants:

            return variants

        page.wait_for_timeout(
            500
        )

    return None


# ============================================================
# FIND VARIANT BY SKU
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
# GET PRICE
#
# Използваме NORMAL price.
#
# При:
#
# price = 1.99
# discountedPrice = 1.99
#
# резултатът е:
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
# GET QUANTITY
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
# GET STORE QUANTITY
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
            ==
            wanted_store.lower()
        ):

            value = store.get(
                "quantity",
                0
            )

            try:

                return int(
                    value
                )

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

def save_results(
    results
):

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
# DEBUG SAVE
# ============================================================

def save_debug(
    page,
    sku
):

    try:

        debug_dir = Path(
            "debug_html"
        )

        debug_dir.mkdir(
            exist_ok=True
        )

        # ----------------------------------------------------
        # HTML
        # ----------------------------------------------------

        html_file = (
            debug_dir /
            f"failed_{sku}.html"
        )

        with open(
            html_file,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(
                page.content()
            )

        # ----------------------------------------------------
        # Screenshot
        # ----------------------------------------------------

        screenshot_file = (
            debug_dir /
            f"failed_{sku}.png"
        )

        page.screenshot(
            path=str(
                screenshot_file
            ),
            full_page=True
        )

        print(
            f"   🐛 Debug запазен:"
        )

        print(
            f"      {html_file}"
        )

        print(
            f"      {screenshot_file}"
        )

    except Exception as e:

        print(
            f"   ⚠️ Debug error: {e}"
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

    # --------------------------------------------------------
    # READ SKU
    # --------------------------------------------------------

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
    # CACHE
    #
    # Product ID -> variants
    #
    # Например:
    #
    # 2557 -> 6 variants
    #
    # Така не отваряме продукта 6 пъти.
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
        # PROCESS SKU
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
            # PRODUCT ID
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

                print()

                continue

            print(
                f"   📦 Product ID: "
                f"{product_id}"
            )

            # =================================================
            # CHECK CACHE
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
                # FIND PRODUCT URL
                # =============================================

                product_url = find_product_url(
                    page,
                    sku,
                    product_id
                )

                if not product_url:

                    print(
                        "   ❌ Product URL "
                        "не е намерен."
                    )

                    not_found.append(
                        sku
                    )

                    print()

                    continue

                print(
                    f"   🌐 {product_url}"
                )

                # =============================================
                # OPEN PRODUCT
                # =============================================

                try:

                    response = page.goto(
                        product_url,
                        wait_until="domcontentloaded",
                        timeout=60000
                    )

                    # -----------------------------------------
                    # Показваме HTTP status
                    # -----------------------------------------

                    if response:

                        print(
                            f"   🌐 Product page "
                            f"HTTP {response.status}"
                        )

                except PlaywrightTimeoutError:

                    print(
                        "   ⚠️ Page timeout."
                    )

                except Exception as e:

                    print(
                        f"   ❌ Page error: "
                        f"{e}"
                    )

                # =============================================
                # WAIT VUE
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
                # VUE NOT FOUND
                # =============================================

                if not variants:

                    print(
                        "   ❌ "
                        "product.variants "
                        "не е намерен."
                    )

                    save_debug(
                        page,
                        sku
                    )

                    not_found.append(
                        sku
                    )

                    print()

                    continue

                # =============================================
                # SAVE CACHE
                # =============================================

                product_cache[
                    product_id
                ] = variants

                print(
                    f"   🔢 Vue variants: "
                    f"{len(variants)}"
                )

            # =================================================
            # FIND EXACT SKU
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

                print()

                continue

            # =================================================
            # BUILD RESULT
            # =================================================

            result = build_result(
                sku,
                product_id,
                variant
            )

            results.append(
                result
            )

            # =================================================
            # PRINT RESULT
            # =================================================

            print(
                f"   ✅ Variant ID: "
                f"{result['Variant ID']}"
            )

            print(
                f"   📦 Бройки: "
                f"{result['Бройки']}"
            )

            print(
                f"   📊 Наличност: "
                f"{result['Наличност']}"
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

            # ------------------------------------------------
            # Optional wait
            # ------------------------------------------------

            if WAIT > 0:

                time.sleep(
                    WAIT
                )

        # ====================================================
        # CLOSE
        # ====================================================

        browser.close()

    # ========================================================
    # SAVE FILES
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


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
