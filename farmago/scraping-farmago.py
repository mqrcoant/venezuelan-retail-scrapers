import requests
from bs4 import BeautifulSoup
import time
import csv
import re
import datetime
# Categorías que obtuvimos de tu navbar
CATEGORIAS_FARMAGO = [
    {"nombre": "Medicamentos", "url": "https://www.farmago.com.ve/shop/category/medicamentos-11"},
    {"nombre": "Salud", "url": "https://www.farmago.com.ve/shop/category/salud-y-primeros-auxilios-12"},
    {"nombre": "Bebé", "url": "https://www.farmago.com.ve/shop/category/bebe-13"},
    {"nombre": "Cuidado Personal", "url": "https://www.farmago.com.ve/shop/category/cuidado-personal-14"},
    {"nombre": "Belleza", "url": "https://www.farmago.com.ve/shop/category/belleza-15"},
    {"nombre": "Hogar", "url": "https://www.farmago.com.ve/shop/category/hogar-y-otros-16"},
    {"nombre": "Alimentos", "url": "https://www.farmago.com.ve/shop/category/alimentos-17"},
    {"nombre": "Bebidas", "url": "https://www.farmago.com.ve/shop/category/bebidas-22"}
]

def scrapear_categoria_farmago(url_categoria, nombre_categoria):
    pagina_actual = 1
    productos_extraidos = []
    
    # Memoria para detectar si Odoo nos repite la página
    skus_pagina_anterior = set() 
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    while True:
        print(f"  -> Extrayendo [{nombre_categoria}] - Página {pagina_actual}...")
        
        if pagina_actual == 1:
            url_paginada = url_categoria
        else:
            url_paginada = f"{url_categoria}/page/{pagina_actual}"
            
        time.sleep(1)
        respuesta = requests.get(url_paginada, headers=headers)
        
        if respuesta.status_code != 200:
            print(f"  Fin de la categoría (Código {respuesta.status_code}).")
            break

        soup = BeautifulSoup(respuesta.text, 'html.parser')
        tarjetas = soup.select('td.oe_product')
        
        if not tarjetas:
            print("  No hay más productos en esta página. Saliendo.")
            break
            
        skus_pagina_actual = set()
            
        for tarjeta in tarjetas:
            elem_btn = tarjeta.select_one('.o_add_wishlist')
            sku_interno = elem_btn.get('data-product-product-id') if elem_btn else None
            
            # Registramos el SKU de esta tarjeta
            if sku_interno:
                skus_pagina_actual.add(sku_interno)
            
            elem_nombre = tarjeta.select_one('[itemprop="name"]')
            nombre = elem_nombre.get('content') if elem_nombre else None
            if not nombre and elem_nombre:
                nombre = elem_nombre.text.strip()
                
            # Buscar el precio final que el usuario ve en pantalla
            elem_precio = tarjeta.select_one('[itemprop="price"]')
            
            if elem_precio:
                precio_base = float(elem_precio.text.strip())
                precio = round(precio_base * 1.00, 2)
            else:
                precio = None
            
            elem_moneda = tarjeta.select_one('[itemprop="priceCurrency"]')
            moneda = elem_moneda.text.strip() if elem_moneda else "VES"

            elem_img = tarjeta.select_one('[itemprop="image"]')
            img_url = f"https://www.farmago.com.ve{elem_img.get('src')}" if elem_img else None
            
            ean = None
            if elem_img and elem_img.get('alt'):
                alt_text = elem_img.get('alt')
                match = re.search(r'\[(\d+)\]', alt_text)
                if match:
                    ean = match.group(1)

            fecha_extraccion = datetime.datetime.now().strftime("%d-%m-%Y")
            
            productos_extraidos.append({
                'categoria': nombre_categoria,
                'ean': ean,
                'sku_interno': sku_interno,
                'nombre': nombre,
                'precio': precio,
                'moneda': moneda,
                'imagen': img_url,
                'fecha_extraccion': fecha_extraccion
            })
            
        # --- FRENO DE EMERGENCIA ANTI-BUCLE ---
        if skus_pagina_actual == skus_pagina_anterior:
            print("  Odoo devolvió los mismos productos que la página anterior. Fin de paginación alcanzado.")
            break
            
        # Actualizamos la memoria para la siguiente iteración
        skus_pagina_anterior = skus_pagina_actual
        pagina_actual += 1

    return productos_extraidos

def guardar_farmago_csv(datos, tasa_bcv, nombre_archivo_con_ean="maestro_farmago.csv", nombre_archivo_sin_ean="pharmago-faltantes.csv"):
    if not datos:
        print("No hay datos para guardar.")
        return

    # Deduplicación por si acaso Odoo repite productos entre páginas
    datos_deduplicados = list({prod['sku_interno']: prod for prod in datos if prod.get('sku_interno')}.values())

    productos_con_ean = []
    productos_sin_ean = []

    for producto in datos_deduplicados:
        # Calcular el precio ref en base a la tasa ingresada
        if producto.get('precio') is not None and tasa_bcv > 0:
            producto['precio_ref'] = round(producto['precio'] / tasa_bcv, 2)
        else:
            producto['precio_ref'] = None

        if producto.get('ean'): 
            productos_con_ean.append(producto)
        else:
            productos_sin_ean.append(producto)

    # Añadida la nueva columna a las cabeceras
    cabeceras = ['categoria', 'ean', 'sku_interno', 'nombre', 'precio', 'moneda', 'precio_ref', 'imagen', 'fecha_extraccion']
    
    if productos_con_ean:
        with open(nombre_archivo_con_ean, mode='w', newline='', encoding='utf-8') as archivo_csv:
            escritor = csv.DictWriter(archivo_csv, fieldnames=cabeceras)
            escritor.writeheader()
            escritor.writerows(productos_con_ean)
        print(f"\n¡Se guardaron {len(productos_con_ean)} productos CON EAN en: {nombre_archivo_con_ean}")

    if productos_sin_ean:
        with open(nombre_archivo_sin_ean, mode='w', newline='', encoding='utf-8') as archivo_csv:
            escritor = csv.DictWriter(archivo_csv, fieldnames=cabeceras)
            escritor.writeheader()
            escritor.writerows(productos_sin_ean)
        print(f"¡Se guardaron {len(productos_sin_ean)} productos SIN EAN en: {nombre_archivo_sin_ean}")

if __name__ == "__main__":
    import os
    # El pipeline inyecta la tasa; la ejecución manual puede solicitarla.
    entrada_tasa = os.environ.get("BCV_RATE") or input("Ingresa la tasa BCV actual: ")
    # Reemplazamos coma por punto por si el usuario se equivoca al escribir el decimal
    entrada_tasa = entrada_tasa.replace(',', '.')
    
    try:
        tasa_bcv_actual = float(entrada_tasa)
    except ValueError as exc:
        raise SystemExit("Tasa BCV inválida: no se publicará un precio convertido incorrecto") from exc
    if tasa_bcv_actual <= 0:
        raise SystemExit("La tasa BCV debe ser positiva")

    print("\nIniciando extracción en Farmago (Odoo)...\n")
    
    todos_los_productos = []
    
    for cat in CATEGORIAS_FARMAGO:
        datos_cat = scrapear_categoria_farmago(cat['url'], cat['nombre'])
        todos_los_productos.extend(datos_cat)
        
    # Pasamos la tasa a la función de guardado
    guardar_farmago_csv(todos_los_productos, tasa_bcv_actual)
