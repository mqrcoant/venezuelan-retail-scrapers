import requests
import time
import csv
from pathlib import Path
from bs4 import BeautifulSoup

CATEGORIAS_EXCLUIDAS = {
    "Perfumes", "Ropa y Calzado", "Hogar & Decoración", 
    "Carteras, Bolsos y Maletas", "Juguetes", "Gift Cards", 
    "Papelería & Arte", "Deportes", "Electrodomésticos", "TV & Electrónica"
}

def obtener_rutas_madison(ruta_html):
    with open(ruta_html, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
        
    rutas_permitidas = []
    enlaces = soup.find_all('a', class_='nav-dropdown__link')
    
    for enlace in enlaces:
        nombre = enlace.text.strip()
        if nombre not in CATEGORIAS_EXCLUIDAS:
            rutas_permitidas.append({
                'categoria': nombre,
                'url_path': enlace.get('href')
            })
            
    return rutas_permitidas

def scrapear_madison_shopify(rutas, dominio):
    productos_extraidos = []
    session = requests.Session()
    
    for ruta in rutas:
        print(f"Extrayendo: {ruta['categoria']}...")
        pagina = 1
        
        while True:
            url_json = f"{dominio}{ruta['url_path']}/products.json?limit=250&page={pagina}"
            
            try:
                for intento in range(3):
                    respuesta = session.get(url_json, timeout=20)
                    if respuesta.status_code != 429:
                        break
                    espera = 10 * (2 ** intento)
                    print(f"     [!] HTTP 429; pausa de {espera}s antes de reintentar")
                    time.sleep(espera)
                if respuesta.status_code != 200:
                    raise RuntimeError(f"HTTP {respuesta.status_code} en {url_json}")
                    
                data = respuesta.json()
                items = data.get('products', [])
                
                if not items:
                    break
                    
                for prod in items:
                    if not prod.get('variants'):
                        continue
                        
                    img_url = prod['images'][0]['src'] if prod.get('images') else None
                    descripcion = BeautifulSoup(prod.get('body_html') or '', 'html.parser').get_text(' ', strip=True)[:30000]
                    for variante in prod['variants']:
                        precio = float(variante.get('price') or 0)
                        if precio <= 0:
                            continue
                        ean = variante.get('barcode')
                        sku = variante.get('sku')
                        id_variante = str(variante.get('id'))
                        titulo_variante = variante.get('title') or ''
                        nombre = prod.get('title') or ''
                        if titulo_variante and titulo_variante != 'Default Title':
                            nombre = f"{nombre} - {titulo_variante}"
                        precio_anterior = float(variante.get('compare_at_price') or 0)
                        productos_extraidos.append({
                            '_id_interno': id_variante,
                            'comercio': 'Madison Center',
                            'departamento': ruta['categoria'],
                            'subcategoria': prod.get('product_type', ruta['categoria']),
                            'marca': prod.get('vendor'),
                            'ean': str(ean).strip() if ean else None,
                            'sku_interno': str(sku).strip() if sku else id_variante,
                            'nombre': nombre,
                            'precio': precio,
                            'precio_anterior': precio_anterior if precio_anterior > precio else None,
                            'disponible': bool(variante.get('available')),
                            'descripcion': descripcion,
                            'actualizado_en_tienda': variante.get('updated_at'),
                            'imagen': img_url
                        })
                    
                pagina += 1
                time.sleep(2)
                
            except Exception as e:
                print(f"     [!] Error de conexión en {ruta['categoria']}: {e}")
                raise
                
    return productos_extraidos

def guardar_madison_csv(datos, archivo="maestro_madison.csv"):
    if not datos: return
    
    # Deduplicamos usando el ID interno de Shopify en memoria
    datos_deduplicados = {p['_id_interno']: p for p in datos}.values()
    
    # Columnas limpias finales (reincorporando sku_interno)
    cabeceras = ['comercio', 'departamento', 'subcategoria', 'marca', 'ean', 'sku_interno', 'nombre', 'precio', 'precio_anterior', 'disponible', 'descripcion', 'actualizado_en_tienda', 'imagen']
    
    with open(archivo, mode='w', newline='', encoding='utf-8') as f:
        escritor = csv.DictWriter(f, fieldnames=cabeceras, extrasaction='ignore')
        escritor.writeheader()
        escritor.writerows(datos_deduplicados)
        
    print(f"\n¡Completado! {len(datos_deduplicados)} productos listos en {archivo}")

if __name__ == "__main__":
    DOMINIO_MADISON = "https://www.madisoncenter.com" 
    
    rutas = obtener_rutas_madison(Path(__file__).resolve().parent / 'navbar-madison.html')
    print(f"Mapeadas {len(rutas)} categorías permitidas.\n")
    
    datos = scrapear_madison_shopify(rutas, DOMINIO_MADISON)
    guardar_madison_csv(datos)
