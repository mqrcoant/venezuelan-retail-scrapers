import requests
from bs4 import BeautifulSoup
import csv
import concurrent.futures

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
    
    try:
        # Usamos session.get en lugar de requests.get
        response = session.get(url_detalle, timeout=10)
        
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
    session.get(BASE_URL)

    with open('catalogo_emporium.csv', mode='w', newline='', encoding='utf-8') as csv_file:
        writer = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(['codigo_interno', 'barcode', 'nombre', 'precio_base_ref', 'precio_final_ref', 'categoria'])

        for cat_code, cat_name in CATEGORIAS.items():
            print(f"\n--- Iniciando extracción de categoría: {cat_name} ---")
            page = 1
            has_next_page = True

            while has_next_page:
                url = f"{BASE_URL}/Products.php?cat={cat_code}&suc=02&Page={page}"
                print(f"Obteniendo lista de productos - Página {page}...")
                
                response = session.get(url)
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
                    print(f"Guardado: {res['nombre'][:30]}... | ${res['precio_base_ref']} | Cod: {res['barcode']}")

                btn_siguiente = soup.find('div', class_='Siguiente')
                if btn_siguiente and 'display: none' not in btn_siguiente.get('style', ''):
                    page += 1
                else:
                    has_next_page = False

if __name__ == "__main__":
    scrapear_catalogo()