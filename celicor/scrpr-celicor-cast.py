import csv
import time
import logging
from curl_cffi import requests

API_URL = "https://celicorlacastellana.com/api/v1/storefront/products"
OUTPUT_FILE = "celicor_la_castellana.csv"
PAGE_SIZE = 48  # Puedes probar 48 o 100 para reducir llamadas

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

session = requests.Session(impersonate="chrome")
session.headers.update({
    "Accept": "application/json",
    "Origin": "https://celicorlacastellana.com",
    "Referer": "https://celicorlacastellana.com/",
})

def parse_pricing_tiers(tiers):
    """
    Convierte la lista de pricingTiers en columnas legibles y raw string.
    """
    res = {
        "precio_1_5": "",
        "precio_6_11": "",
        "precio_12_mas": "",
        "tiers_raw": ""
    }
    if not tiers:
        return res

    raw_parts = []
    for tier in tiers:
        min_q = tier.get("minQty")
        max_q = tier.get("maxQty")
        price = tier.get("unitPrice")
        
        label = f"{min_q}-{max_q}" if max_q else f"+{min_q}"
        raw_parts.append(f"{label}={price}")

        if min_q == 1 and max_q == 5:
            res["precio_1_5"] = price
        elif min_q == 6 and max_q == 11:
            res["precio_6_11"] = price
        elif min_q in (12, 6) and (max_q is None or max_q >= 12):
            res["precio_12_mas"] = price

    res["tiers_raw"] = " | ".join(raw_parts)
    return res

def scrape_celicor():
    page = 1
    all_products = []

    while True:
        logging.info("Consultando página %s...", page)
        params = {
            "pageSize": PAGE_SIZE,
            "page": page
        }

        resp = session.get(API_URL, params=params)
        if resp.status_code != 200:
            logging.error("Error HTTP %s en página %s", resp.status_code, page)
            break

        data = resp.json()
        items = data.get("items", [])
        if not items:
            break

        for item in items:
            tiers_data = parse_pricing_tiers(item.get("pricingTiers", []))
            
            product_data = {
                "id": item.get("id", ""),
                "ean_sku": item.get("sku") or "",
                "nombre": item.get("name", ""),
                "marca": item.get("brand") or "",
                "categoria": item.get("category", ""),
                "categoria_id": item.get("categoryId", ""),
                "tamano": item.get("size", ""),
                "precio_base": item.get("price", ""),
                "precio_caja": item.get("casePrice", ""),
                "unidades_por_caja": item.get("unitsPerCase", ""),
                "precio_1_5": tiers_data["precio_1_5"],
                "precio_6_11": tiers_data["precio_6_11"],
                "precio_12_mas": tiers_data["precio_12_mas"],
                "precios_tier_raw": tiers_data["tiers_raw"],
                "stock": item.get("stock", ""),
                "imagen_uri": item.get("image", ""),
                "slug": item.get("slug", ""),
                "url_producto": f"https://celicorlacastellana.com/producto/{item.get('slug', '')}" if item.get("slug") else ""
            }
            all_products.append(product_data)

        logging.info("  %s productos obtenidos en esta página (Total: %s)", len(items), len(all_products))

        if not data.get("hasMore", False):
            logging.info("No hay más páginas disponibles.")
            break

        page += 1
        time.sleep(0.5)

    # Guardar a CSV
    if all_products:
        fieldnames = list(all_products[0].keys())
        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_products)
        logging.info("Guardados %s productos en %s", len(all_products), OUTPUT_FILE)

if __name__ == "__main__":
    scrape_celicor()