import requests
import time
import csv
import datetime
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def obtener_arbol_categorias_locatel():
    print("Mapeando el árbol de categorías de Locatel...")
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    url = "https://www.locatel.com.ve/api/catalog_system/pub/category/tree/3"
    
    respuesta = requests.get(url, headers=headers)
    if respuesta.status_code == 200:
        return respuesta.json()
    else:
        print(f"Error al obtener el árbol: {respuesta.status_code}")
        return []

def extraer_rutas_hojas(categorias, departamento_raiz=None, rutas=None):
    if rutas is None:
        rutas = []
        
    for cat in categorias:
        raiz = departamento_raiz if departamento_raiz else cat.get('name')
        
        if cat.get('hasChildren') and cat.get('children'):
            extraer_rutas_hojas(cat['children'], raiz, rutas)
        else:
            url_completa = cat.get('url', '')
            path_limpio = urlparse(url_completa).path.strip('/')
            
            if path_limpio:
                rutas.append({
                    'departamento': raiz,
                    'subcategoria': cat.get('name'),
                    'path': path_limpio
                })
                
    return rutas

def scrapear_subcategoria_locatel(path_categoria, departamento, subcategoria):
    productos_extraidos = []
    inicio = 0
    paso = 49 # Locatel permite paginar de 50 en 50
    
    session = requests.Session()
    estrategia_reintentos = Retry(
        total=4, 
        backoff_factor=2, 
        status_forcelist=[429, 500, 502, 503, 504], 
        allowed_methods=["GET"]
    )
    session.mount("https://", HTTPAdapter(max_retries=estrategia_reintentos))
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}

    while True:
        print(f"  -> [{departamento} > {subcategoria}] | Ítems {inicio} al {inicio + paso}...")
        url = f"https://www.locatel.com.ve/api/catalog_system/pub/products/search/{path_categoria}?_from={inicio}&_to={inicio + paso}"
        
        time.sleep(1.5) 
        
        try:
            respuesta = session.get(url, headers=headers, timeout=15)
        except requests.exceptions.ConnectionError:
            print("     [!] Corte de conexión. Saltando bloque.")
            inicio += 50
            continue
        except requests.exceptions.Timeout:
            print("     [!] Timeout. Saltando.")
            inicio += 50
            continue
            
        if respuesta.status_code not in [200, 206]:
            break
            
        datos = respuesta.json()
        if not datos:
            break 
            
        for prod in datos:
            marca = prod.get('brand')
            nombre = prod.get('productName')
            referencia_interna = prod.get('productReference') or prod.get('productId')
            
            precio_base_ves = None
            precio_con_iva_ves = None
            precio_ref = None
            img_url = None
            ean = None
            
            for item in prod.get('items', []):
                if not ean:
                    ean = item.get('ean')
                if not img_url and item.get('images'):
                    img_url = item['images'][0].get('imageUrl')
                
                for vendedor in item.get('sellers', []):
                    oferta = vendedor.get('commertialOffer', {})
                    p_base = oferta.get('Price', 0)
                    impuesto = oferta.get('Tax', 0)
                    
                    if p_base > 0:
                        precio_base_ves = p_base
                        precio_con_iva_ves = round(p_base + impuesto, 2)
                        precio_ref = round(precio_con_iva_ves / TASA_BCV, 2)
                        break
                        
                if precio_base_ves:
                    break 
            
            if not precio_base_ves or precio_base_ves <= 0:
                continue
                
            fecha_extraccion = datetime.datetime.now().strftime("%Y-%m-%d")
            
            productos_extraidos.append({
                'comercio': 'Locatel',
                'departamento': departamento,
                'subcategoria': subcategoria,
                'marca': marca,
                'ean': ean,
                'sku_interno': referencia_interna,
                'nombre': nombre,
                'precio_base_ves': precio_base_ves,
                'precio_con_iva_ves': precio_con_iva_ves,
                'precio_ref': precio_ref,
                'imagen': img_url,
                'fecha_extraccion': fecha_extraccion
            })
            
        inicio += 50

    return productos_extraidos

def guardar_locatel_csv(datos, nombre_archivo_con_sku="prods_locatel.csv", nombre_archivo_sin_sku="locatel-faltantes.csv"):
    if not datos:
        print("No hay datos para guardar.")
        return

    productos_con_sku = []
    productos_sin_sku = []
    skus_vistos = set()

    for prod in datos:
        sku = prod.get('sku_interno')
        if sku:
            if sku not in skus_vistos:
                skus_vistos.add(sku)
                productos_con_sku.append(prod)
        else:
            productos_sin_sku.append(prod)

    cabeceras = ['comercio', 'departamento', 'subcategoria', 'marca', 'ean', 'sku_interno', 'nombre', 'precio_base_ves', 'precio_con_iva_ves', 'precio_ref', 'imagen', 'fecha_extraccion']
    
    if productos_con_sku:
        with open(nombre_archivo_con_sku, mode='w', newline='', encoding='utf-8') as archivo_csv:
            escritor = csv.DictWriter(archivo_csv, fieldnames=cabeceras)
            escritor.writeheader()
            escritor.writerows(productos_con_sku)
        print(f"\n¡Se guardaron {len(productos_con_sku)} productos CON SKU en: {nombre_archivo_con_sku}")

    if productos_sin_sku:
        with open(nombre_archivo_sin_sku, mode='w', newline='', encoding='utf-8') as archivo_csv:
            escritor = csv.DictWriter(archivo_csv, fieldnames=cabeceras)
            escritor.writeheader()
            escritor.writerows(productos_sin_sku)
        print(f"¡Se guardaron {len(productos_sin_sku)} productos SIN SKU en: {nombre_archivo_sin_sku}")

if __name__ == "__main__":
    tasa_input = input("Ingresa la tasa BCV de hoy (ej. 36.65): ")
    TASA_BCV = float(tasa_input.replace(',', '.'))
    arbol = obtener_arbol_categorias_locatel()
    rutas_a_scrapear = extraer_rutas_hojas(arbol)
    
    print(f"Detectadas {len(rutas_a_scrapear)} subcategorías en Locatel.\n")
    todos_los_productos = []
    
    for ruta in rutas_a_scrapear:
        datos_ruta = scrapear_subcategoria_locatel(ruta['path'], ruta['departamento'], ruta['subcategoria'])
        todos_los_productos.extend(datos_ruta)
        
    guardar_locatel_csv(todos_los_productos)