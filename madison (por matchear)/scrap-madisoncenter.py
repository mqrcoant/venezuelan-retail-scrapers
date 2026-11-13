import requests
import time
import csv
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
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for ruta in rutas:
        print(f"Extrayendo: {ruta['categoria']}...")
        pagina = 1
        
        while True:
            url_json = f"{dominio}{ruta['url_path']}/products.json?limit=250&page={pagina}"
            
            try:
                respuesta = requests.get(url_json, headers=headers, timeout=10)
                if respuesta.status_code != 200:
                    break
                    
                data = respuesta.json()
                items = data.get('products', [])
                
                if not items:
                    break
                    
                for prod in items:
                    if not prod.get('variants'):
                        continue
                        
                    variante_principal = prod['variants'][0]
                    
                    if not variante_principal.get('available'):
                        continue
                        
                    precio = float(variante_principal.get('price', 0))
                    
                    if precio <= 0:
                        continue
                        
                    img_url = prod['images'][0]['src'] if prod.get('images') else None
                    ean = variante_principal.get('barcode')
                    sku = variante_principal.get('sku')
                    id_variante = str(variante_principal.get('id'))
                    
                    productos_extraidos.append({
                        '_id_interno': id_variante, 
                        'comercio': 'Madison Center',
                        'departamento': ruta['categoria'],
                        'subcategoria': prod.get('product_type', ruta['categoria']),
                        'marca': prod.get('vendor'),
                        'ean': str(ean).strip() if ean else None,
                        'sku_interno': str(sku).strip() if sku else id_variante,
                        'nombre': prod.get('title'),
                        'precio': precio,
                        'imagen': img_url
                    })
                    
                pagina += 1
                time.sleep(1) 
                
            except Exception as e:
                print(f"     [!] Error de conexión en {ruta['categoria']}: {e}")
                break
                
    return productos_extraidos

def guardar_madison_csv(datos, archivo="maestro_madison.csv"):
    if not datos: return
    
    # Deduplicamos usando el ID interno de Shopify en memoria
    datos_deduplicados = {p['_id_interno']: p for p in datos}.values()
    
    # Columnas limpias finales (reincorporando sku_interno)
    cabeceras = ['comercio', 'departamento', 'subcategoria', 'marca', 'ean', 'sku_interno', 'nombre', 'precio', 'imagen']
    
    with open(archivo, mode='w', newline='', encoding='utf-8') as f:
        escritor = csv.DictWriter(f, fieldnames=cabeceras, extrasaction='ignore')
        escritor.writeheader()
        escritor.writerows(datos_deduplicados)
        
    print(f"\n¡Completado! {len(datos_deduplicados)} productos listos en {archivo}")

if __name__ == "__main__":
    DOMINIO_MADISON = "https://www.madisoncenter.com" 
    
    rutas = obtener_rutas_madison('C:\\Users\\USUARIO\\Documents\\1. Work\\Kuantip\\scripts\\madison\\navbar-madison.html')
    print(f"Mapeadas {len(rutas)} categorías permitidas.\n")
    
    datos = scrapear_madison_shopify(rutas, DOMINIO_MADISON)
    guardar_madison_csv(datos)