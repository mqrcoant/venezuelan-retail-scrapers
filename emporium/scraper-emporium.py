import requests
from bs4 import BeautifulSoup
import csv
import concurrent.futures
import json
import os
import re
import time
from pathlib import Path

CHECKPOINT = Path(__file__).resolve().parent.parent / 'logs' / 'emporium_checkpoint.json'
CSV_PATH = Path(__file__).resolve().parent / 'catalogo_emporium.csv'
BARCODES_PATH = CHECKPOINT.parent / 'emporium_barcodes_historicos.json'
barcodes_cache = {}


def get_con_reintentos(url, timeout=40):
    for intento in range(3):
        try:
            respuesta = session.get(url, timeout=timeout)
            if respuesta.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f'HTTP {respuesta.status_code} en {url}')
            return respuesta
        except requests.RequestException:
            if intento == 2:
                raise
            time.sleep(2 * (intento + 1))

BASE_URL = "https://automercadosemporium.com"

# 1. Configurar una Sesión Persistente con cabeceras robustas
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
    "Referer": f"{BASE_URL}/"
})

CATEGORIAS = {
    "01ASEO": "ASEO",
    "02HOGA": "HOGAR",
    "03CARN": "CARNICERIA",
    "04VIVE": "VIVERES",
    "05CHAR": "CHARCUTERIA",
    "06CONG": "CONGELADOS",
    "07CUID": "CUIDADO PERSONAL",
    "08FRUV": "FRUTAS Y VERDURAS",
    "09CAFE": "CAFETERIA",
    "10LICO": "LICORERIA",
    "11MASC": "MASCOTAS",
    "13REFR": "REFRIGERADOS",
    "14AUTO": "AUTOMOTRIZ MOTOS"
}

def extraer_detalle_producto(producto):
    """Worker para multithreading: Visita la URL de detalle usando la sesión global."""
    url_detalle = f"{BASE_URL}/Product.php?code={producto['codigo_interno']}"
    if producto['codigo_interno'] in barcodes_cache:
        producto['barcode'] = barcodes_cache[producto['codigo_interno']]
        return producto
    
    try:
        # Usamos session.get en lugar de requests.get
        response = get_con_reintentos(url_detalle, timeout=15)
        
        # Opcional: imprimir el status_code en caso de error para depurar
        if response.status_code != 200:
            producto['barcode'] = f"HTTP_{response.status_code}"
            return producto
            
        soup = BeautifulSoup(response.text, 'html.parser')
        span_codigo = soup.find('span', class_='bar_code_span')
        
        if span_codigo and span_codigo.text.strip():
            producto['barcode'] = span_codigo.text.strip()
        else:
            producto['barcode'] = "No_Encontrado" 
            
    except Exception as e:
        producto['barcode'] = "Error_Timeout"
        
    return producto

def scrapear_catalogo():
    # Hacemos una petición inicial a la home para capturar cualquier cookie necesaria
    print("Inicializando sesión y capturando cookies...")
    get_con_reintentos(BASE_URL).raise_for_status()

    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    if BARCODES_PATH.exists():
        barcodes_cache.update(json.loads(BARCODES_PATH.read_text(encoding='utf-8')))
    if CSV_PATH.exists():
        with CSV_PATH.open(newline='', encoding='utf-8-sig') as entrada:
            barcodes_cache.update({fila['codigo_interno']: fila['barcode'] for fila in csv.DictReader(entrada)
                                   if re.fullmatch(r'\d{8,14}', fila['barcode'] or '')})
    print(f'{len(barcodes_cache)} códigos de barras históricos disponibles')
    reanudar = os.environ.get('EMPORIUM_RESUME') == '1' and CHECKPOINT.exists() and CSV_PATH.exists()
    estado = json.loads(CHECKPOINT.read_text(encoding='utf-8')) if reanudar else {'categoria': 0, 'pagina': 1}
    vistos = set()
    if reanudar:
        with CSV_PATH.open(newline='', encoding='utf-8') as entrada:
            vistos = {fila['codigo_interno'] for fila in csv.DictReader(entrada)}
        print(f'Reanudando desde {estado}; {len(vistos)} productos guardados')

    with CSV_PATH.open(mode='a' if reanudar else 'w', newline='', encoding='utf-8') as csv_file:
        writer = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        if not reanudar:
            writer.writerow(['codigo_interno', 'barcode', 'nombre', 'precio_base_ref', 'precio_final_ref', 'categoria'])

        for indice, (cat_code, cat_name) in enumerate(CATEGORIAS.items()):
            if indice < estado['categoria']:
                continue
            print(f"\n--- Iniciando extracción de categoría: {cat_name} ---")
            page = estado['pagina'] if indice == estado['categoria'] else 1
            has_next_page = True

            while has_next_page:
                url = f"{BASE_URL}/Products.php?cat={cat_code}&suc=02&Page={page}"
                print(f"Obteniendo lista de productos - Página {page}...")
                
                response = get_con_reintentos(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                productos_html = soup.find_all('div', class_='groups-product-item')
                
                if not productos_html:
                    break
                
                productos_en_pagina = []
                
                for prod in productos_html:
                    btn_add = prod.find('button', class_='btnAdded')
                    if not btn_add:
                        continue
                        
                    codigo_interno = btn_add['onclick'].split("'")[1]
                    if codigo_interno in vistos:
                        continue
                    nombre_tag = prod.find('p', id='nombre_producto')
                    precio_tag = prod.find('p', id='tag_precio_producto')
                    
                    nombre = nombre_tag.text.strip() if nombre_tag else "Sin Nombre"
                    precio_ref = float(precio_tag.text.strip().replace('$', '')) if precio_tag else 0.0

                    productos_en_pagina.append({
                        'codigo_interno': codigo_interno,
                        'nombre': nombre,
                        'precio_base_ref': precio_ref,
                        'precio_final_ref': precio_ref,
                        'categoria': cat_name,
                        'barcode': '' 
                    })

                # Mantenemos los hilos a un nivel conservador (5) para evitar ser bloqueados por rate-limiting
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    resultados = list(executor.map(extraer_detalle_producto, productos_en_pagina))
                
                for res in resultados:
                    writer.writerow([
                        res['codigo_interno'], res['barcode'], res['nombre'], 
                        res['precio_base_ref'], res['precio_final_ref'], res['categoria']
                    ])
                    vistos.add(res['codigo_interno'])
                    print(f"Guardado: {res['nombre'][:30]}... | ${res['precio_base_ref']} | Cod: {res['barcode']}")

                btn_siguiente = soup.find('div', class_='Siguiente')
                if btn_siguiente and 'display: none' not in btn_siguiente.get('style', ''):
                    page += 1
                    siguiente = {'categoria': indice, 'pagina': page}
                else:
                    has_next_page = False
                    siguiente = {'categoria': indice + 1, 'pagina': 1}
                csv_file.flush()
                CHECKPOINT.write_text(json.dumps(siguiente), encoding='utf-8')
            if not productos_html:
                CHECKPOINT.write_text(json.dumps({'categoria': indice + 1, 'pagina': 1}), encoding='utf-8')
    CHECKPOINT.unlink(missing_ok=True)

if __name__ == "__main__":
    scrapear_catalogo()
