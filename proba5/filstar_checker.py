import csv
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


BASE_URL = "https://filstar.com"

INPUT_FILE = "sku_list_filstar.csv"
OUTPUT_FILE = "results_filstar.csv"
NOT_FOUND_FILE = "not_found_filstar.csv"

# За тестове е 0.
# По-късно може да го направим 1-2 секунди.
WAIT = 0


# ============================================================
# ЧЕТЕНЕ НА SKU
#
# Правило:
#
# SKU
# 946537
# 946534
# ##
# 946535
# 946536
# ##
#
# Всичко между две ## линии се игнорира.
#
# Това позволява временно да изключваме големи групи SKU.
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

            first = str(
                row[0]
            ).strip()

            # Празен ред
            if not first:
                continue

            # ------------------------------------------------
            # ## включва/изключва коментарния блок
            # ------------------------------------------------

            if first == "##":

                in_comment_block = not in_comment_block
                continue

            # ------------------------------------------------
            # Всичко вътре в ## ... ## се пропуска
            # ------------------------------------------------

            if in_comment_block:
                continue

            # ------------------------------------------------
            # Header
            # ------------------------------------------------

            if first.lower() == "sku":
                continue

            # ------------------------------------------------
            # Взимаме само първата колона
            # ------------------------------------------------

            sku = first.strip()

            if sku:
                skus.append(sku)

    return skus


# ============================================================
# FIND PRODUCT ID
#
# /api/search е достъпен и го използваме само за намиране
# на parent product ID.
#
# Например:
#
# SKU 946537
#       ↓
# product_id 2557
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
            f"   /api/search -> "
            f"HTTP {response.status}"
        )

        if response.status != 200:
            return None

        html = response.text()

        # Търсим:
        #
        # data-product-id="2557"
        #

        matches = re.findall(
            r'data-product-id=["\'](\d+)["\']',
            html
        )

        if not matches:
            return None

        # Премахваме дублиращите се ID-та,
        # като запазваме реда.
        unique_ids = list(
            dict.fromkeys(matches)
        )

        # Ако има няколко продукта,
        # търсим този, в чийто HTML има SKU.
        for product_id in unique_ids:

            pattern = (
                rf'data-product-id=["\']'
                rf'{re.escape(product_id)}'
                rf'["\']'
                rf'[^>]*'
            )

            product_match = re.search(
                pattern,
                html,
                re.IGNORECASE
            )

            if product_match:

                # Взимаме малко по-голям контекст
                # около product card-а.
                start = max(
                    0,
                    product_match.start() - 500
                )

                end = min(
                    len(html),
                    product_match.end() + 5000
                )

                context = html[
                    start:end
                ]

                if sku in context:
                    return product_id

        # При нашия тест /api/search обикновено
        # връща правилния product като първи.
        return unique_ids[0]

    except Exception as e:

        print(
            f"   ❌ Грешка при /api/search: {e}"
        )

        return None


# ============================================================
# FIND PRODUCT URL
#
# От /api/search намираме реалния href на продукта.
#
# Например:
#
# /Muhi-za-buldo-bz
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

        html = response.text

        # ----------------------------------------------------
        # Търсим href.
        # ----------------------------------------------------

        hrefs = re.findall(
            r'href=["\']([^"\']+)["\']',
            html,
            re.IGNORECASE
        )

        for href in hrefs:

            href = href.strip()

            if not href:
                continue

            # Вътрешен URL
            if href.startswith("/"):
                full_url = (
                    BASE_URL + href
                )

            # Пълен URL
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

            # ------------------------------------------------
            # Това трябва да е продуктовият URL.
            # ------------------------------------------------

            return full_url

        return None

    except Exception as e:

        print(
            f"   ❌ Грешка при URL: {e}"
        )

        return None


# ============================================================
# ЧЕТЕМ VUE PRODUCT.VARIANTS
#
# Това е най-важната част.
#
# В Console установихме:
#
# document.querySelectorAll("*")[544].__vue__
#
# и:
#
# v.product
# v.product.variants
#
# Тук НЕ правим API parser на variant JSON.
#
# Оставяме страницата да зареди Vue и директно четем
# неговия state от DOM.
# ============================================================

def extract_variants_from_vue(page):

    variants = page.evaluate(
        """
        () => {

            const elements =
                document.querySelectorAll("*");

            for (const el of elements) {

                const vue = el.__vue__;

                if (!vue) {
                    continue;
                }

                // Точно това търсихме в Console:
                //
                // v.product
                // v.product.variants
                //

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

    return variants


# ============================================================
# WAIT FOR VUE
#
# Vue може да не е зареден веднага.
# Проверяваме многократно, но не чакаме излишно.
# ============================================================

def wait_for_vue_variants(page):

    for attempt in range(15):

        variants = (
            extract_variants_from_vue(
                page
            )
        )

        if variants:
            return variants

        # 500 ms между проверките
        page.wait_for_timeout(500)

    return None


# ============================================================
# FIND VARIANT BY SKU
#
# Това е еквивалентът на Vue кода:
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
# Ако няма price, имаме fallback към discountedPrice.
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

    if quantity > 0:
        availability = "Наличен"
    else:
        availability = "Изчерпан"

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
            sofia
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

        "София"
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
    # Cache:
    #
    # product_id -> variants
    #
    # Един продукт може да има много SKU.
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

        # ----------------------------------------------------
        # Обработваме SKU
        # ----------------------------------------------------

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
                    "   ❌ Product ID не е намерен."
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
            # 2. ПРОВЕРЯВАМЕ CACHE
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
                        "   ❌ Product URL не е намерен."
                    )

                    not_found.append(
                        sku
                    )

                    continue

                print(
                    f"   🌐 {product_url}"
                )

                # =============================================
                # 4. ОТВАРЯМЕ СТРАНИЦАТА
                # =============================================

                try:

                    page.goto(
                        product_url,
                        wait_until="domcontentloaded",
                        timeout=60000
                    )

                except PlaywrightTimeoutError:

                    print(
                        "   ⚠️ Page timeout."
                    )

                # =============================================
                # 5. ЧАКАМЕ VUE
                # =============================================

                print(
                    "   ⏳ Чакам Vue..."
                )

                variants = (
                    wait_for_vue_variants(
                        page
                    )
                )

                # =============================================
                # 6. АКО НЯМА VUE
                # =============================================

                if not variants:

                    print(
                        "   ❌ Не намерих "
                        "Vue product.variants."
                    )

                    # ------------------------------------------------
                    # Debug screenshot + HTML
                    # само при грешка
                    # ------------------------------------------------

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
                    f"   🔢 Намерени variants: "
                    f"{len(variants)}"
                )

            # =================================================
            # 8. НАМИРАМЕ SKU В VARIANTS
            # =================================================

            variant = find_variant(
                variants,
                sku
            )

            if not variant:

                print(
                    "   ❌ SKU не съществува "
                    "в product.variants."
                )

                not_found.append(
                    sku
                )

                continue

            # =================================================
            # 9. ИЗВЛИЧАМЕ ДАННИТЕ
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
                time.sleep(WAIT)

        # ----------------------------------------------------
        # Browser close
        # ----------------------------------------------------

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
