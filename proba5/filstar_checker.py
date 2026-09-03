import os
import re
import csv
import json
import html
import requests
from bs4 import BeautifulSoup, Comment

BASE_URL = "https://filstar.com"
CSV_FILE = "sku_list_filstar.csv"
DEBUG_DIR = "debug_html"

WAIT = 2

TEST_SKUS = [
    "946537",
    "946534",
    "946535",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "bg-BG,bg;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    value = html.unescape(str(value))
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def save_text(filename, content):
    path = os.path.join(DEBUG_DIR, filename)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return path


def read_skus():
    skus = []

    if not os.path.exists(CSV_FILE):
        print(f"❌ CSV файлът не съществува: {CSV_FILE}")
        return skus

    with open(CSV_FILE, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)

        for row in reader:
            if not row:
                continue

            value = row[0].strip()

            if not value:
                continue

            # Пропускаме header
            if value.lower() in (
                "sku",
                "код",
                "product sku",
                "product_sku",
            ):
                continue

            # Пропускаме коментари
            if value.startswith("#"):
                continue

            skus.append(value)

    return skus


# ============================================================
# API SEARCH
# ============================================================

def search_filstar(session, sku):
    url = f"{BASE_URL}/api/search"

    params = {
        "term": sku
    }

    try:
        response = session.get(
            url,
            params=params,
            headers=HEADERS,
            timeout=30
        )

        print(
            f"   🔎 /api/search?term={sku} → "
            f"HTTP {response.status_code}"
        )

        print(
            f"   Content-Type: "
            f"{response.headers.get('Content-Type', '')}"
        )

        print(
            f"   Размер: {len(response.content):,} bytes"
        )

        return response

    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return None


# ============================================================
# EXACT SKU LOCATIONS
# ============================================================

def find_exact_occurrences(source, sku):
    """
    Намира ВСИЧКИ срещания на SKU в целия HTML.
    """

    positions = []

    start = 0

    while True:
        pos = source.find(sku, start)

        if pos == -1:
            break

        positions.append(pos)
        start = pos + len(sku)

    return positions


# ============================================================
# DETECT SCRIPT / STYLE / COMMENT
# ============================================================

def detect_container_type(source, position):
    """
    Опитва се да разбере дали позицията е:

    - normal HTML
    - script
    - style
    - comment
    """

    before = source[:position]

    last_script_open = before.rfind("<script")
    last_script_close = before.rfind("</script")

    last_style_open = before.rfind("<style")
    last_style_close = before.rfind("</style")

    last_comment_open = before.rfind("<!--")
    last_comment_close = before.rfind("-->")

    # SCRIPT
    if last_script_open > last_script_close:
        return "SCRIPT"

    # STYLE
    if last_style_open > last_style_close:
        return "STYLE"

    # COMMENT
    if last_comment_open > last_comment_close:
        return "HTML COMMENT"

    return "NORMAL HTML"


# ============================================================
# GET TAG AROUND POSITION
# ============================================================

def get_tag_around_position(source, position):
    """
    Взима приблизително HTML tag-а, в който се намира SKU-то.
    """

    left = source.rfind("<", 0, position)
    right = source.find(">", position)

    if left == -1 or right == -1:
        return ""

    tag = source[left:right + 1]

    # Ако е прекалено голямо нещо, ограничаваме
    if len(tag) > 5000:
        return tag[:5000] + "\n...[TAG TRUNCATED]..."

    return tag


# ============================================================
# GET OPENING TAGS / PARENT CONTEXT
# ============================================================

def get_parent_tags(source, position, max_tags=12):
    """
    Опитва се да намери последните отворени HTML елементи
    преди позицията.

    Не е пълен HTML parser, а диагностичен анализ.
    """

    before = source[:position]

    tags = re.findall(
        r"<([a-zA-Z][a-zA-Z0-9:-]*)\b[^>]*>",
        before
    )

    closing = re.findall(
        r"</([a-zA-Z][a-zA-Z0-9:-]*)\s*>",
        before
    )

    # По-груба информация:
    # показваме последните tags преди SKU
    result = []

    pattern = re.compile(
        r"</?[a-zA-Z][^>]*>"
    )

    all_tags = list(pattern.finditer(before))

    for match in all_tags[-max_tags:]:
        tag = match.group(0)

        if len(tag) > 1000:
            tag = tag[:1000] + "..."

        result.append(tag)

    return result


# ============================================================
# BEAUTIFULSOUP CONTEXT
# ============================================================

def soup_context(source, sku, occurrence_index):
    """
    Използва BeautifulSoup за намиране на елементите,
    които съдържат SKU-то.
    """

    soup = BeautifulSoup(source, "html.parser")

    results = []

    # Всички елементи, чието text съдържа SKU
    for element in soup.find_all(string=lambda x: x and sku in x):

        parent = element.parent

        if parent is None:
            continue

        results.append({
            "string": clean_text(str(element)),
            "parent_tag": parent.name,
            "parent_attributes": dict(parent.attrs),
            "parent_html": str(parent)[:10000]
        })

    return results


# ============================================================
# DATA ATTRIBUTES
# ============================================================

def extract_data_attributes(tag_html):
    """
    Извлича всички data-* атрибути.
    """

    result = {}

    matches = re.findall(
        r'(data-[\w:-]+)\s*=\s*["\']([^"\']*)["\']',
        tag_html,
        flags=re.I
    )

    for key, value in matches:
        result[key] = html.unescape(value)

    return result


# ============================================================
# ATTRIBUTES
# ============================================================

def extract_attributes(tag_html):
    """
    Извлича атрибутите от HTML tag.
    """

    result = {}

    if not tag_html.startswith("<"):
        return result

    match = re.match(
        r"<\s*([a-zA-Z0-9:-]+)",
        tag_html
    )

    if not match:
        return result

    result["_tag"] = match.group(1)

    attributes = re.findall(
        r'([a-zA-Z_:][a-zA-Z0-9_:\-.]*)\s*=\s*["\']([^"\']*)["\']',
        tag_html
    )

    for key, value in attributes:
        result[key] = html.unescape(value)

    return result


# ============================================================
# OCCURRENCE ANALYSIS
# ============================================================

def analyze_occurrence(source, sku, occurrence_index, position):
    context_size = 1500

    start = max(0, position - context_size)
    end = min(
        len(source),
        position + len(sku) + context_size
    )

    before = source[start:position]
    after = source[
        position + len(sku):end
    ]

    full_context = source[start:end]

    container_type = detect_container_type(
        source,
        position
    )

    tag = get_tag_around_position(
        source,
        position
    )

    attributes = extract_attributes(tag)

    data_attributes = extract_data_attributes(tag)

    parent_tags = get_parent_tags(
        source,
        position
    )

    result = []

    result.append("=" * 100)
    result.append(
        f"OCCURRENCE #{occurrence_index}"
    )
    result.append("=" * 100)

    result.append(
        f"SKU: {sku}"
    )

    result.append(
        f"Character position: {position:,}"
    )

    result.append(
        f"Container type: {container_type}"
    )

    result.append("")

    result.append(
        "-------------------- EXACT TAG --------------------"
    )

    result.append(tag)

    result.append("")

    result.append(
        "-------------------- ATTRIBUTES --------------------"
    )

    if attributes:
        result.append(
            json.dumps(
                attributes,
                ensure_ascii=False,
                indent=2
            )
        )
    else:
        result.append("NO ATTRIBUTES FOUND")

    result.append("")

    result.append(
        "-------------------- DATA-* ATTRIBUTES --------------------"
    )

    if data_attributes:
        result.append(
            json.dumps(
                data_attributes,
                ensure_ascii=False,
                indent=2
            )
        )
    else:
        result.append("NO DATA ATTRIBUTES")

    result.append("")

    result.append(
        "-------------------- PREVIOUS HTML TAGS --------------------"
    )

    for i, parent in enumerate(parent_tags, 1):
        result.append(
            f"[{i}] {parent}"
        )

    result.append("")

    result.append(
        "-------------------- CONTEXT BEFORE --------------------"
    )

    result.append(before)

    result.append("")

    result.append(
        "-------------------- SKU --------------------"
    )

    result.append(sku)

    result.append("")

    result.append(
        "-------------------- CONTEXT AFTER --------------------"
    )

    result.append(after)

    result.append("")

    result.append(
        "-------------------- FULL CONTEXT --------------------"
    )

    result.append(full_context)

    return "\n".join(result)


# ============================================================
# SEARCH FOR RELATED SKU / NUMBERS
# ============================================================

def extract_numbers_near_sku(source, sku, position):
    """
    Извлича всички числа в +/- 1500 символа
    около SKU-то.
    """

    start = max(
        0,
        position - 1500
    )

    end = min(
        len(source),
        position + len(sku) + 1500
    )

    context = source[start:end]

    numbers = re.findall(
        r"\b\d{2,}\b",
        context
    )

    # unique, запазваме реда
    unique = []

    for number in numbers:
        if number not in unique:
            unique.append(number)

    return unique


# ============================================================
# FULL SKU ANALYSIS
# ============================================================

def analyze_sku(source, sku):
    print()
    print("=" * 60)
    print(f"SKU ANALYSIS: {sku}")
    print("=" * 60)

    positions = find_exact_occurrences(
        source,
        sku
    )

    print(
        f"Exact occurrences: {len(positions)}"
    )

    if not positions:
        print(
            f"❌ SKU {sku} не е намерено."
        )
        return

    all_results = []

    # --------------------------------------------------------
    # Общ файл
    # --------------------------------------------------------

    summary = []

    summary.append(
        f"SKU: {sku}"
    )

    summary.append(
        f"Total occurrences: {len(positions)}"
    )

    summary.append("")

    # --------------------------------------------------------
    # Всеки occurrence
    # --------------------------------------------------------

    for index, position in enumerate(
        positions,
        start=1
    ):

        container_type = detect_container_type(
            source,
            position
        )

        tag = get_tag_around_position(
            source,
            position
        )

        attributes = extract_attributes(tag)

        data_attributes = extract_data_attributes(
            tag
        )

        numbers = extract_numbers_near_sku(
            source,
            sku,
            position
        )

        print()
        print(
            f"   #{index}: position={position:,}"
        )

        print(
            f"      Type: {container_type}"
        )

        if tag:
            print(
                f"      Tag: {tag[:500]}"
            )

        if data_attributes:
            print(
                "      data-*:"
            )

            for key, value in data_attributes.items():
                print(
                    f"         {key} = {value}"
                )

        print(
            f"      Numbers nearby: "
            f"{', '.join(numbers)}"
        )

        result = analyze_occurrence(
            source,
            sku,
            index,
            position
        )

        all_results.append(result)

        summary.append(
            f"OCCURRENCE #{index}"
        )

        summary.append(
            f"Position: {position}"
        )

        summary.append(
            f"Type: {container_type}"
        )

        summary.append(
            f"Tag: {tag}"
        )

        summary.append(
            "Attributes:"
        )

        summary.append(
            json.dumps(
                attributes,
                ensure_ascii=False,
                indent=2
            )
        )

        summary.append(
            "Data attributes:"
        )

        summary.append(
            json.dumps(
                data_attributes,
                ensure_ascii=False,
                indent=2
            )
        )

        summary.append(
            "Numbers nearby:"
        )

        summary.append(
            ", ".join(numbers)
        )

        summary.append("")
        summary.append("-" * 100)
        summary.append("")

    # --------------------------------------------------------
    # BeautifulSoup analysis
    # --------------------------------------------------------

    print()
    print(
        "   🔬 BeautifulSoup text-node analysis..."
    )

    soup_results = soup_context(
        source,
        sku,
        len(positions)
    )

    print(
        f"   BeautifulSoup matches: "
        f"{len(soup_results)}"
    )

    summary.append("")
    summary.append(
        "=" * 100
    )
    summary.append(
        "BEAUTIFULSOUP MATCHES"
    )
    summary.append(
        "=" * 100
    )

    for i, item in enumerate(
        soup_results,
        start=1
    ):

        summary.append(
            f"\nMATCH #{i}"
        )

        summary.append(
            f"String: {item['string']}"
        )

        summary.append(
            f"Parent tag: {item['parent_tag']}"
        )

        summary.append(
            "Parent attributes:"
        )

        summary.append(
            json.dumps(
                item["parent_attributes"],
                ensure_ascii=False,
                indent=2
            )
        )

        summary.append(
            "Parent HTML:"
        )

        summary.append(
            item["parent_html"]
        )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    full_output = "\n\n".join(
        all_results
    )

    save_text(
        f"context_{sku}.txt",
        full_output
    )

    save_text(
        f"context_{sku}_summary.txt",
        "\n".join(summary)
    )

    # --------------------------------------------------------
    # Raw context around ALL occurrences
    # --------------------------------------------------------

    raw_context = []

    for index, position in enumerate(
        positions,
        start=1
    ):

        start = max(
            0,
            position - 5000
        )

        end = min(
            len(source),
            position + len(sku) + 5000
        )

        raw_context.append(
            f"\n\n{'=' * 100}\n"
            f"OCCURRENCE #{index}\n"
            f"POSITION: {position}\n"
            f"{'=' * 100}\n\n"
            f"{source[start:end]}"
        )

    save_text(
        f"context_{sku}_raw_5000.txt",
        "".join(raw_context)
    )

    print()
    print(
        f"   💾 Saved:"
    )

    print(
        f"      debug_html/context_{sku}.txt"
    )

    print(
        f"      debug_html/context_{sku}_summary.txt"
    )

    print(
        f"      debug_html/context_{sku}_raw_5000.txt"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("FILSTAR SKU CONTEXT DIAGNOSTIC")
    print("=" * 70)

    os.makedirs(
        DEBUG_DIR,
        exist_ok=True
    )

    skus = read_skus()

    print(
        f"🧾 Общо SKU: {len(skus)}"
    )

    print(
        f"🧪 Тестови SKU: "
        f"{', '.join(TEST_SKUS)}"
    )

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    for index, sku in enumerate(
        TEST_SKUS,
        start=1
    ):

        print()
        print("=" * 70)
        print(
            f"SKU {index}/{len(TEST_SKUS)}: {sku}"
        )
        print("=" * 70)

        response = search_filstar(
            session,
            sku
        )

        if response is None:
            continue

        source = response.text

        # ----------------------------------------------------
        # SAVE RAW SEARCH
        # ----------------------------------------------------

        raw_file = save_text(
            f"search_{sku}.html",
            source
        )

        print(
            f"   💾 Raw HTML: {raw_file}"
        )

        # ----------------------------------------------------
        # ANALYZE SKU
        # ----------------------------------------------------

        analyze_sku(
            source,
            sku
        )

    print()
    print("=" * 70)
    print("DIAGNOSTIC FINISHED")
    print("=" * 70)

    print(
        f"Debug folder: {DEBUG_DIR}"
    )

    print()
    print(
        "Следващото, което ни интересува:"
    )

    print(
        "1. context_946537.txt"
    )

    print(
        "2. context_946534.txt"
    )

    print(
        "3. context_946535.txt"
    )

    print()
    print(
        "Особено важно е какъв е EXACT TAG / Container type "
        "при occurrence-ите на 946534 и 946535."
    )


if __name__ == "__main__":
    main()
