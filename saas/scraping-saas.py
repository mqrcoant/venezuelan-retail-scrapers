import datetime
import requests
import time
import csv
from urllib.parse import urlparse


def obtener_arbol_categorias():
    """Obtiene la estructura completa de la base de datos de VTEX"""
    print("Mapeando el árbol de categorías de Farmacia SAAS...")
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    
    # El /3 al final indica la profundidad (Departamentos > Categorías > Subcategorías)
    url = "https://www.farmaciasaas.com/api/catalog_system/pub/category/tree/3"
    
    respuesta = requests.get(url, headers=headers)
    if respuesta.status_code == 200:
        return respuesta.json()
    else:
        print(f"Error al obtener el árbol: {respuesta.status_code}")
        return []


def extraer_rutas_hojas(categorias, departamento_raiz=None, rutas=None):
    """Filtra las subcategorías más pequeñas (hojas) para burlar el límite de 2500 ítems"""
    if rutas is None:
        rutas = []
        
    for cat in categorias:
        # Mantenemos el nombre del departamento principal (Ej. Alimentos)
        raiz = departamento_raiz if departamento_raiz else cat.get('name')
        
        if cat.get('hasChildren') and cat.get('children'):
            # Si tiene hijos, entramos más profundo
            extraer_rutas_hojas(cat['children'], raiz, rutas)
        else:
            # Si no tiene hijos, es una subcategoría final (Ej. Galletas)
            url_completa = cat.get('url', '')
            path_limpio = urlparse(url_completa).path.strip('/')
            
            if path_limpio:
                rutas.append({
                    'departamento': raiz,
                    'subcategoria': cat.get('name'),
                    'path': path_limpio
                })
                
    return rutas


def scrapear_subcategoria(path_categoria, departamento, subcategoria):
    productos_extraidos = []
    inicio = 0
    paso = 23  # VTEX funciona de 24 en 24
    
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}

    while True:
        print(f"  -> Extrayendo [{departamento} > {subcategoria}] | Ítems {inicio} al {inicio + paso}...")
        
        url = f"https://www.farmaciasaas.com/api/catalog_system/pub/products/search/{path_categoria}?_from={inicio}&_to={inicio + paso}"
        
        time.sleep(1)  # Pausa por cortesía
        respuesta = requests.get(url, headers=headers)
        
        # Aceptamos 200 y 206 (Contenido Parcial)
        if respuesta.status_code not in [200, 206]:
            print(f"     Error {respuesta.status_code} en la ruta. Saltando.")
            break
            
        datos = respuesta.json()
        
        if not datos:
            break  # Ya no hay más productos en esta subcategoría
            
        for prod in datos:
            marca = prod.get('brand')
            nombre = prod.get('productName')
            referencia_interna = prod.get('productReference') or prod.get('productId')
            
            precio_base = None
            precio_final = None
            img_url = None
            ean = None
            oferta = {}
            
            # Iteramos sobre todos los ítems (variantes) del producto
            for item in prod.get('items', []):
                
                # Extraemos EAN e imagen del primer ítem válido que encontremos
                if not ean:
                    ean = item.get('ean')
                if not img_url and item.get('images'):
                    img_url = item['images'][0].get('imageUrl')
                
                # Iteramos sobre TODOS los vendedores para encontrar el precio activo
                for vendedor in item.get('sellers', []):
                    oferta = vendedor.get('commertialOffer', {})
                    p_base = oferta.get('Price', 0)
                    impuesto = oferta.get('Tax', 0)
                    
                    if p_base > 0:
                        precio_base = p_base
                        precio_final = round(p_base + impuesto, 2)
                        break  # Encontramos el precio real, rompemos el ciclo de vendedores
                
                if precio_base:
                    break
                        
            fecha_extraccion = datetime.datetime.now().strftime("%d-%m-%Y")

            # --- EMPAQUETADO FINAL ---
            productos_extraidos.append({
                'departamento': departamento,
                'subcategoria': subcategoria,
                'marca': marca,
                'ean': ean,
                'sku_interno': referencia_interna,
                'nombre': nombre,
                'precio_base': precio_base,
                'precio_con_iva': precio_final,
                'imagen': img_url,
                'fecha_extraccion': fecha_extraccion
            })
                
        inicio += 24

    return productos_extraidos


def guardar_saas_csv(datos, nombre_archivo_completos="prods_saas.csv", nombre_archivo_faltantes="saas-faltantes.csv"):
    if not datos:
        print("No hay datos para guardar.")
        return

    productos_completos = []
    productos_faltantes = []
    
    # Para deduplicar los que sí tienen sku
    skus_vistos = set()

    for prod in datos:
        sku = prod.get('sku_interno')
        ean = prod.get('ean')
        
        # Exigimos que AMBOS campos existan y no estén vacíos
        if sku and ean:
            if sku not in skus_vistos:
                skus_vistos.add(sku)
                productos_completos.append(prod)
        else:
            # Si falta el SKU o falta el EAN, se va a la lista de revisión
            productos_faltantes.append(prod)

    cabeceras = ['departamento', 'subcategoria', 'marca', 'ean', 'sku_interno', 'nombre', 'precio_base', 'precio_con_iva', 'imagen', 'fecha_extraccion']
    
    if productos_completos:
        with open(nombre_archivo_completos, mode='w', newline='', encoding='utf-8') as archivo_csv:
            escritor = csv.DictWriter(archivo_csv, fieldnames=cabeceras)
            escritor.writeheader()
            escritor.writerows(productos_completos)
        print(f"\n¡Se guardaron {len(productos_completos)} productos COMPLETOS (con SKU y EAN) en: {nombre_archivo_completos}")

    if productos_faltantes:
        with open(nombre_archivo_faltantes, mode='w', newline='', encoding='utf-8') as archivo_csv:
            escritor = csv.DictWriter(archivo_csv, fieldnames=cabeceras)
            escritor.writeheader()
            escritor.writerows(productos_faltantes)
        print(f"¡Se guardaron {len(productos_faltantes)} productos INCOMPLETOS (sin SKU o EAN) en: {nombre_archivo_faltantes}")


if __name__ == "__main__":
    print("Iniciando modo de extracción granular de VTEX...\n")
    
    # 1. Obtener el árbol y aplanarlo
    arbol = obtener_arbol_categorias()
    rutas_a_scrapear = extraer_rutas_hojas(arbol)
    
    # --- INYECCIÓN MANUAL DE CATEGORÍAS FALTANTES ---
    rutas_a_scrapear.append({
        'departamento': 'Mascotas',
        'subcategoria': 'General',
        'path': 'mascotas'
    })
    
    print(f"Se identificaron {len(rutas_a_scrapear)} subcategorías en la tienda.\n")
    
    todos_los_productos_saas = []
    
    # 2. Iterar sobre cada subcategoría pequeña
    for ruta in rutas_a_scrapear:
        datos_ruta = scrapear_subcategoria(ruta['path'], ruta['departamento'], ruta['subcategoria'])
        todos_los_productos_saas.extend(datos_ruta)
        
    # 3. Guardar y deduplicar
    guardar_saas_csv(todos_los_productos_saas)