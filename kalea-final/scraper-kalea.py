import requests
import time
import re
import os
import pandas as pd

API_BASE = "https://mywkxuvnbnzfxdbswojh.supabase.co/rest/v1"
API_KEY = "sb_publishable_kBqxEZ84Hm_AIwHrj0YEIg_LUG4c21B"

HEADERS = {
    "apikey": API_KEY,
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json",
    "Prefer": "count=none"
}

STORES = {
    "caracas": "fe596136-c2fd-4890-89f2-730e429f9635",
    "carabobo": "06fa9d16-998a-483f-900c-4532e60ef5cd"
}

def get_exchange_rate():
    """Obtiene la tasa de cambio vigente (usd_to_ves_rate) desde Supabase"""
    url = f"{API_BASE}/exchange_rates"
    params = {
        "select": "usd_to_ves_rate,effective_date",
        "order": "effective_date.desc",
        "limit": 1
    }
    r = requests.get(url, headers=HEADERS, params=params)
    data = r.json()
    if data and "usd_to_ves_rate" in data[0]:
        rate = float(data[0]["usd_to_ves_rate"])
        print(f"[*] Tasa de cambio cargada: 1 USD = {rate:.2f} VES")
        return rate
    print("[!] No se pudo obtener la tasa, usando fallback de 1.0")
    return 1.0

def limpiar_ean(ean_raw):
    """Elimina absolutamente cualquier espacio en blanco dentro del string."""
    return re.sub(r'\s+', '', str(ean_raw or ""))

def validar_ean(ean):
    """Verifica que el EAN contenga solo dígitos y tenga entre 4 y 13 caracteres."""
    return ean.isdigit() and 4 <= len(ean) <= 13

def exportar_xlsx(nombre_archivo, datos, columnas):
    """Función auxiliar para exportar las listas a XLSX en la ruta absoluta especificada"""
    if datos:
        # 1. Ruta absoluta de Kuantip
        carpeta = r"C:\\Users\\USUARIO\\Documents\\1. Work\\Kuantip\\scripts\\kalea-final"
        os.makedirs(carpeta, exist_ok=True)
        
        # 2. Construir la ruta completa
        ruta_completa = os.path.join(carpeta, nombre_archivo)
        
        # 3. Exportar a Excel usando pandas
        df = pd.DataFrame(datos, columns=columnas)
        df.to_excel(ruta_completa, index=False)
        print(f"  [+] Guardado: {ruta_completa} ({len(datos)} registros)")

def scrape_kalea_catalog(store_name, store_id, rate):
    print(f"\n[*] Extrayendo y procesando: {store_name.upper()}")
    
    productos_estandar = []
    productos_ecom = []
    productos_faltantes = []
    
    offset = 0
    limit = 1000

    while True:
        params = {
            "select": "barcode,name,brand,department,group_name,thumbnail_url,presentation,product_type,multiplier,inventory!inner(store_id,price_base,price,quantity),offers(*)",
            "active": "eq.true",
            "inventory.store_id": f"eq.{store_id}",
            "limit": limit,
            "offset": offset
        }
        
        res = requests.get(f"{API_BASE}/products", headers=HEADERS, params=params)
        if res.status_code != 200:
            print(f"[!] Error HTTP {res.status_code}: {res.text}")
            break
            
        data = res.json()
        if not data:
            break
            
        for item in data:
            inv = item.get("inventory", [{}])[0] if item.get("inventory") else {}
            stock_actual = inv.get("quantity", 0)
            price_base_bs = float(inv.get("price_base") or 0.0)
            
            # 1. Precios y Ofertas
            raw_final_price = float(inv.get("price") or price_base_bs)
            offers = item.get("offers", [])
            if offers and offers[0].get("offer_price"):
                raw_final_price = float(offers[0].get("offer_price"))

            # 2. Normalización de Moneda
            if price_base_bs > 0 and raw_final_price < (price_base_bs / 10):
                price_final_ref = raw_final_price
                price_final_bs = raw_final_price * rate
            else:
                price_final_bs = raw_final_price
                price_final_ref = raw_final_price / rate if rate else 0.0

            price_base_ref = price_base_bs / rate if rate else 0.0

            # 3. Cálculo de precio por KG
            presentation = str(item.get("presentation") or "").upper()
            product_type = str(item.get("product_type") or "").upper()
            
            try:
                multiplier = float(item.get("multiplier") or 1.0)
            except ValueError:
                multiplier = 1.0

            price_kg_bs = ""
            price_kg_ref = ""
            if (presentation == "KG" or product_type == "PESABLE") and multiplier > 0:
                price_kg_bs = round(price_final_bs / multiplier, 2)
                price_kg_ref = round(price_final_ref / multiplier, 2)

            # 4. Limpieza de EAN y Nombre (E-COM)
            ean_limpio = limpiar_ean(item.get("barcode"))
            nombre = str(item.get("name") or "").strip()
            es_ecom = False
            
            # Verificar si contiene la etiqueta e-com (case-insensitive)
            if re.search(r'(?i)\b(?:ecom|e-com|e_com)\b', nombre):
                es_ecom = True
                # Remover etiqueta y arreglar dobles espacios
                nombre_limpio = re.sub(r'(?i)\s*\b(?:ecom|e-com|e_com)\b\s*', ' ', nombre)
                nombre = re.sub(r'\s+', ' ', nombre_limpio).strip()

            # Diccionario final del producto
            prod_dict = {
                "ean": ean_limpio,
                "name": nombre,
                "brand": item.get("brand"),
                "department": item.get("department"),
                "category": item.get("group_name"),
                "quantity": stock_actual,
                "price_base_bs": round(price_base_bs, 2),
                "price_final_bs": round(price_final_bs, 2),
                "price_base_ref": round(price_base_ref, 2),
                "price_final_ref": round(price_final_ref, 2),
                "price_kg_bs": price_kg_bs,
                "price_kg_ref": price_kg_ref,
                "image_url": item.get("thumbnail_url") or "N/A"
            }

            # 5. Distribución en listas
            if not validar_ean(ean_limpio):
                productos_faltantes.append(prod_dict)
            elif es_ecom:
                productos_ecom.append(prod_dict)
            else:
                productos_estandar.append(prod_dict)
        
        print(f"  -> Procesados {len(data)} items en esta página (Offset: {offset})")
        offset += limit
        time.sleep(0.2)
        
    # Exportar los archivos para esta sede
    # (Asegúrate de agregar 'stock' en tus columnas si seguiste el paso anterior)
    columnas = [
        "ean", "name", "brand", "department", "category", "quantity",
        "price_base_bs", "price_final_bs", "price_base_ref", "price_final_ref", 
        "price_kg_bs", "price_kg_ref", "stock", "image_url" 
    ]
    
    exportar_xlsx(f"kalea_{store_name}_estandar.xlsx", productos_estandar, columnas)
    exportar_xlsx(f"kalea_{store_name}_ecom.xlsx", productos_ecom, columnas)
    exportar_xlsx(f"kalea_{store_name}_faltantes.xlsx", productos_faltantes, columnas)

if __name__ == "__main__":
    current_rate = get_exchange_rate()
    for name, s_id in STORES.items():
        scrape_kalea_catalog(name, s_id, current_rate)