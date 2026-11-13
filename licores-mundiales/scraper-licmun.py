import csv
import re
import time
import random
import logging
from collections import defaultdict
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from playwright_stealth import stealth

from urllib.parse import urljoin, urlparse, urlencode
from playwright.sync_api import sync_playwright


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_URL = "https://www.licoresmundiales.com"
OUTPUT_FILE = "licores_mundiales.csv"

PRODUCTS_PER_PAGE = 200

REQUEST_DELAY_MIN = 0.8
REQUEST_DELAY_MAX = 1.8

TIMEOUT = 30
MAX_RETRIES = 3

SCRAPE_SKU = True
SCRAPE_SUBCATEGORIES = True

# Para pruebas puedes limitar categorías:
# ONLY_CATEGORIES = {"Vinos"}
ONLY_CATEGORIES = None


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


# ============================================================
# PLAYWRIGHT SETUP
# ============================================================
playwright_context = None
browser = None
context = None
page = None

import playwright_stealth
from playwright.sync_api import sync_playwright

def init_browser():
    global playwright_context, browser, context, page
    playwright_context = sync_playwright().start()
    
    # El argumento desactiva la bandera de automatización en Blink
    browser = playwright_context.chromium.launch(
        headless=False,
        args=["--disable-blink-features=AutomationControlled"]
    )
    
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080}
    )
    
    # Elimina la huella 'webdriver' de Javascript antes de cargar la web
    context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    page = context.new_page()

def close_browser():
    if browser:
        browser.close()
    if playwright_context:
        playwright_context.stop()


# ============================================================
# UTILIDADES
# ============================================================

def sleep_random():
    time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))


def clean_text(text):
    if text is None:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def parse_price(text):
    """
    '$  49,50' -> 49.50
    """
    if not text:
        return ""

    text = text.replace("$", "").strip()
    text = text.replace(".", "").replace(",", ".")

    match = re.search(r"\d+(?:\.\d+)?", text)

    if not match:
        return ""

    try:
        return float(match.group())
    except ValueError:
        return ""


def normalize_sku(sku):
    if not sku:
        return ""

    sku = clean_text(sku)
    return re.sub(r"\s+", "-", sku)


def get_soup(url, params=None):
    if params:
        query_string = urlencode(params)
        url = f"{url}?{query_string}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # domcontentloaded es más rápido que esperar a que cargue toda la red
            response = page.goto(url, timeout=TIMEOUT * 1000, wait_until="domcontentloaded")
            
            # Pausa humana aleatoria
            page.wait_for_timeout(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX) * 1000)

            if response and response.status == 200:
                return BeautifulSoup(page.content(), "html.parser")

            logging.warning(
                "HTTP %s en %s | intento %s/%s",
                response.status if response else "None",
                url,
                attempt,
                MAX_RETRIES
            )

        except Exception as e:
            logging.warning(
                "Error en %s | intento %s/%s | %s",
                url,
                attempt,
                MAX_RETRIES,
                e
            )

        time.sleep(attempt * 2)

    return None


# ============================================================
# DESCUBRIR MENÚ / CATEGORÍAS
# ============================================================

def discover_catalog():
    """
    Lee el menú principal y devuelve:

    categories = {
        "Vinos": {
            "url": ".../vinos.html",
            "slug": "vinos",
            "subcategories": [
                {
                    "grupo": "Tipos",
                    "nombre": "Tintos",
                    "url": ".../vinos/tipos/tintos.html"
                },
                ...
            ]
        }
    }
    """

    logging.info("Leyendo menú principal...")

    soup = get_soup(BASE_URL)

    if not soup:
        raise RuntimeError("No se pudo cargar la página principal.")

    nav = soup.select_one("nav.sw-megamenu")

    if not nav:
        raise RuntimeError(
            "No pude localizar nav.sw-megamenu. "
            "Puede haber cambiado la estructura."
        )

    categories = {}

    for li0 in nav.select(":scope > ul > li.level0"):

        top_a = li0.select_one(":scope > a.level-top")

        if not top_a:
            continue

        category_name = clean_text(top_a.get_text())
        category_url = urljoin(BASE_URL, top_a.get("href", ""))

        if ONLY_CATEGORIES and category_name not in ONLY_CATEGORIES:
            continue

        path = urlparse(category_url).path.strip("/")
        slug = path.split("/")[0].replace(".html", "")

        subcategories = []

        for li1 in li0.select("li.level1"):

            group_a = li1.select_one(":scope > a")

            if not group_a:
                continue

            group_name = clean_text(group_a.get_text())

            level2_links = li1.select(":scope li.level2 > a")

            # Caso normal: Grupo -> subcategorías
            if level2_links:

                for a in level2_links:

                    name = clean_text(a.get_text())
                    url = urljoin(BASE_URL, a.get("href", ""))

                    subcategories.append({
                        "grupo": group_name,
                        "nombre": name,
                        "url": url
                    })

            else:
                # Algunas categorías tienen nivel1 sin nivel2
                url = urljoin(BASE_URL, group_a.get("href", ""))

                if url != category_url:
                    subcategories.append({
                        "grupo": "Subcategoría",
                        "nombre": group_name,
                        "url": url
                    })

        categories[category_name] = {
            "url": category_url,
            "slug": slug,
            "subcategories": subcategories
        }

    return categories


# ============================================================
# PARSEO DE PRODUCTOS
# ============================================================

def parse_short_description(text):
    """
    Ejemplos:

    España | 2024 | 0.75 Lt
    España | 0.75 Lt
    """

    result = {
        "pais": "",
        "anio": "",
        "volumen": ""
    }

    if not text:
        return result

    parts = [
        clean_text(x)
        for x in text.split("|")
        if clean_text(x)
    ]

    for part in parts:

        if re.fullmatch(r"(19|20)\d{2}", part):
            result["anio"] = part

        elif re.search(
            r"\b(?:ml|cl|lt|l|litro|litros)\b",
            part,
            re.I
        ):
            result["volumen"] = part

        elif not result["pais"]:
            result["pais"] = part

    return result


def parse_tier_prices(product):
    tiers = []

    for li in product.select(
        ".tier-prices .tier-item:not(.title)"
    ):

        units_el = li.select_one(".units")
        price_el = li.select_one(".price")

        if not units_el or not price_el:
            continue

        units = clean_text(units_el.get_text())
        price = parse_price(price_el.get_text())

        tiers.append({
            "units": units,
            "price": price
        })

    return tiers


def classify_common_tiers(tiers):
    """
    Devuelve las columnas específicas solicitadas.

    Ejemplos reconocidos:

    1 - 5
    6 - 11
    + 12
    +12
    12+
    """

    result = {
        "precio_1_5": "",
        "precio_6_11": "",
        "precio_12_mas": ""
    }

    for tier in tiers:

        units = (
            tier["units"]
            .lower()
            .replace(" ", "")
            .replace("–", "-")
        )

        price = tier["price"]

        if units in {
            "1-5",
            "1a5"
        }:
            result["precio_1_5"] = price

        elif units in {
            "6-11",
            "6a11"
        }:
            result["precio_6_11"] = price

        elif (
            units in {"+12", "12+"}
            or re.fullmatch(r"\+?12(?:omás)?", units)
        ):
            result["precio_12_mas"] = price

    return result


def extract_image_sku(image_url):
    """
    Fallback.

    001-006-386.jpg -> 001-006-386
    """

    if not image_url:
        return ""

    filename = urlparse(image_url).path.split("/")[-1]

    filename = re.sub(
        r"\.(jpg|jpeg|png|webp)$",
        "",
        filename,
        flags=re.I
    )

    # Quitar sufijos comunes de imágenes
    filename = re.sub(
        r"(?:_1|_2|v1|v2)+$",
        "",
        filename,
        flags=re.I
    )

    if re.fullmatch(r"\d{3}[-_]\d{3}[-_]\d+", filename):
        return filename.replace("_", "-")

    return ""


def parse_product_card(product, category_name):

    product_id = product.get("data-product-id", "")

    name_el = product.select_one(
        ".product-item-name .product-item-link"
    )

    if not name_el:
        return None

    name = clean_text(name_el.get_text())

    product_url = urljoin(
        BASE_URL,
        name_el.get("href", "")
    )

    image_el = product.select_one("img.product-image-photo")

    image_url = ""

    if image_el:
        image_url = (
            image_el.get("src")
            or image_el.get("data-src")
            or ""
        )

    description_el = product.select_one(
        ".lm-short-description"
    )

    short_desc = (
        clean_text(description_el.get_text())
        if description_el
        else ""
    )

    info = parse_short_description(short_desc)

    # Precio principal mostrado
    price_el = product.select_one(
        ".prices .price-box .price"
    )

    precio_base = (
        parse_price(price_el.get_text())
        if price_el
        else ""
    )

    tiers = parse_tier_prices(product)

    common_tiers = classify_common_tiers(tiers)

    tiers_raw = "|".join(
        f"{tier['units']}={tier['price']}"
        for tier in tiers
    )

    sku_fallback = extract_image_sku(image_url)

    return {
        "_product_id": product_id,

        "sku_interno": sku_fallback,
        "nombre": name,
        "categoria_principal": category_name,

        "subcategorias": "",
        "tipo": "",
        "origen": "",
        "cepa": "",
        "marca": "",

        "pais": info["pais"],
        "anio": info["anio"],
        "volumen": info["volumen"],

        "precio_base": precio_base,
        "precio_1_5": common_tiers["precio_1_5"],
        "precio_6_11": common_tiers["precio_6_11"],
        "precio_12_mas": common_tiers["precio_12_mas"],

        "precios_tier_raw": tiers_raw,
        "atributos_categoria": "",

        "url_producto": product_url,
        "url_imagen": image_url
    }


# ============================================================
# PAGINACIÓN
# ============================================================

def scrape_category_products(
    category_name,
    category_url,
    collect_full_data=True
):
    """
    Devuelve diccionario:
        product_id -> datos

    collect_full_data=False:
        sirve para páginas de subcategorías.
        Solo nos interesa product_id.
    """

    products = {}

    page = 1

    while True:

        logging.info(
            "%s | página %s",
            category_name,
            page
        )

        params = {
            "p": page,
            "product_list_limit": PRODUCTS_PER_PAGE
        }

        soup = get_soup(
            category_url,
            params=params
        )

        if not soup:
            break

        cards = soup.select(
            "li.item.product.product-item[data-product-id]"
        )

        if not cards:

            # Selector alternativo
            cards = soup.select(
                "li.product-item[data-product-id]"
            )

        if not cards:
            break

        new_ids = 0

        for card in cards:

            product_id = card.get(
                "data-product-id",
                ""
            )

            if not product_id:
                continue

            if product_id in products:
                continue

            new_ids += 1

            if collect_full_data:

                parsed = parse_product_card(
                    card,
                    category_name
                )

                if parsed:
                    products[product_id] = parsed

            else:
                products[product_id] = True

        logging.info(
            "  Encontrados %s productos nuevos",
            new_ids
        )

        if new_ids == 0:
            break

        # Si llegaron menos que el límite solicitado,
        # probablemente es la última página.
        if len(cards) < PRODUCTS_PER_PAGE:
            break

        page += 1

        sleep_random()

    return products


# ============================================================
# SKU DESDE LA FICHA
# ============================================================

def scrape_product_sku(url, fallback=""):

    if not SCRAPE_SKU:
        return fallback

    soup = get_soup(url)

    if not soup:
        return fallback

    selectors = [
        '[itemprop="sku"]',
        '.product.attribute.sku .value',
        '[data-product-sku]'
    ]

    for selector in selectors:

        elements = soup.select(selector)

        for element in elements:

            sku = ""

            if element.has_attr("data-product-sku"):
                sku = element.get(
                    "data-product-sku",
                    ""
                )
            else:
                sku = clean_text(
                    element.get_text()
                )

            sku = clean_text(sku)

            if sku:
                return normalize_sku(sku)

    return fallback


# ============================================================
# NORMALIZACIÓN DE GRUPOS
# ============================================================

def normalize_group(group):
    group_low = group.lower().strip()

    mappings = {
        "tipo": "tipo",
        "tipos": "tipo",

        "origen": "origen",

        "cepa": "cepa",

        "marca": "marca",
        "marcas": "marca",
    }

    return mappings.get(group_low)


# ============================================================
# ASOCIAR SUBCATEGORÍAS
# ============================================================

def scrape_subcategory_memberships(
    categories,
    catalog
):
    """
    catalog:
        product_id -> producto

    Va recorriendo cada subcategoría y guarda
    las asociaciones mediante product_id.
    """

    memberships = defaultdict(
        lambda: defaultdict(set)
    )

    for category_name, category in categories.items():

        for sub in category["subcategories"]:

            group = sub["grupo"]
            name = sub["nombre"]
            url = sub["url"]

            logging.info(
                "Subcategoría: %s > %s > %s",
                category_name,
                group,
                name
            )

            sub_products = scrape_category_products(
                f"{category_name}/{group}/{name}",
                url,
                collect_full_data=False
            )

            for product_id in sub_products:

                # Solo asociamos a productos
                # encontrados en catálogo principal
                if product_id not in catalog:
                    continue

                memberships[product_id][group].add(
                    name
                )

            sleep_random()

    return memberships


def apply_memberships(
    catalog,
    memberships
):

    for product_id, product in catalog.items():

        groups = memberships.get(
            product_id,
            {}
        )

        all_subcats = []
        attrs = []

        for group, values in groups.items():

            values_sorted = sorted(values)

            for value in values_sorted:

                all_subcats.append(value)

                attrs.append(
                    f"{group}: {value}"
                )

            canonical = normalize_group(group)

            if canonical:

                product[canonical] = "|".join(
                    values_sorted
                )

        product["subcategorias"] = "|".join(
            sorted(set(all_subcats))
        )

        product["atributos_categoria"] = (
            " | ".join(attrs)
        )


# ============================================================
# CSV
# ============================================================

CSV_COLUMNS = [
    "sku_interno",
    "nombre",
    "categoria_principal",
    "subcategorias",
    "tipo",
    "origen",
    "cepa",
    "marca",
    "pais",
    "anio",
    "volumen",
    "precio_base",
    "precio_1_5",
    "precio_6_11",
    "precio_12_mas",
    "precios_tier_raw",
    "atributos_categoria",
    "url_producto",
    "url_imagen",
]


def save_csv(catalog):

    rows = list(catalog.values())

    rows.sort(
        key=lambda x: (
            x.get(
                "categoria_principal",
                ""
            ),
            x.get(
                "nombre",
                ""
            )
        )
    )

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=CSV_COLUMNS,
            extrasaction="ignore"
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(row)

    logging.info(
        "CSV guardado: %s",
        OUTPUT_FILE
    )

    logging.info(
        "Total productos: %s",
        len(rows)
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("SCRAPER LICORES MUNDIALES")
    print("=" * 70)
    print()

    init_browser()

    try:

        # --------------------------------------------------------
        # 1. Descubrir categorías
        # --------------------------------------------------------

        categories = discover_catalog()

        print(
            f"Categorías encontradas: "
            f"{len(categories)}"
        )

        for name in categories:
            print(
                f" - {name}: "
                f"{len(categories[name]['subcategories'])} "
                f"subcategorías"
            )

        print()

        # --------------------------------------------------------
        # 2. Productos principales
        # --------------------------------------------------------

        catalog = {}

        for category_name, category in categories.items():

            logging.info(
                "=== CATEGORÍA %s ===",
                category_name
            )

            category_products = (
                scrape_category_products(
                    category_name,
                    category["url"],
                    collect_full_data=True
                )
            )

            for product_id, product in (
                category_products.items()
            ):

                if product_id not in catalog:
                    catalog[product_id] = product

                else:
                    # En caso raro de aparecer en
                    # más de una categoría principal
                    existing = catalog[
                        product_id
                    ][
                        "categoria_principal"
                    ]

                    categories_existing = set(
                        existing.split("|")
                    )

                    categories_existing.add(
                        category_name
                    )

                    catalog[
                        product_id
                    ][
                        "categoria_principal"
                    ] = "|".join(
                        sorted(categories_existing)
                    )

            sleep_random()

        print()
        print(
            f"Productos únicos encontrados: "
            f"{len(catalog)}"
        )
        print()

        # --------------------------------------------------------
        # 3. Subcategorías
        # --------------------------------------------------------

        if SCRAPE_SUBCATEGORIES:

            logging.info(
                "=== ANALIZANDO SUBCATEGORÍAS ==="
            )

            memberships = (
                scrape_subcategory_memberships(
                    categories,
                    catalog
                )
            )

            apply_memberships(
                catalog,
                memberships
            )

        # --------------------------------------------------------
        # 4. SKU desde fichas individuales
        # --------------------------------------------------------

        if SCRAPE_SKU:

            logging.info(
                "=== OBTENIENDO SKU INTERNOS ==="
            )

            total = len(catalog)

            for i, (
                product_id,
                product
            ) in enumerate(
                catalog.items(),
                1
            ):

                logging.info(
                    "SKU %s/%s | %s",
                    i,
                    total,
                    product["nombre"]
                )

                product[
                    "sku_interno"
                ] = scrape_product_sku(
                    product[
                        "url_producto"
                    ],
                    product[
                        "sku_interno"
                    ]
                )

                sleep_random()

                # Guardado parcial cada 100 productos
                if i % 100 == 0:
                    save_csv(catalog)

        # --------------------------------------------------------
        # 5. Guardar
        # --------------------------------------------------------

        save_csv(catalog)

    finally:
        close_browser()

    print()
    print("=" * 70)
    print("TERMINADO")
    print("=" * 70)
    print(
        f"Archivo: {OUTPUT_FILE}"
    )
    print(
        f"Productos: {len(catalog)}"
    )
    print()


if __name__ == "__main__":
    main()