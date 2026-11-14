import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import csv
import json
import os
import time
from pathlib import Path

CHECKPOINT = Path(__file__).resolve().parent.parent / 'logs' / 'superfresh_checkpoint.json'
CSV_PATH = Path(__file__).resolve().parent / 'maestro_super_fresh_market.csv'

def scrapear_super_fresh_market():
    categorias = [
        "frutas-y-verduras", "carniceria", "viveres", "charcuteria", 
        "panaderia", "limpieza-del-hogar", "salud-y-belleza", 
        "bebidas-snacks-y-dulces", "congelados", "mascotas", 
        "lacteos-y-huevos", "hogar", "combos-fresh", "licores"
    ]

    base_url = "https://superfreshmarket.com.ve/categoria-producto/"

    print("Iniciando navegador fantasma (Chrome parcheado)...")
    opciones = uc.ChromeOptions()
    opciones.add_argument('--headless') 
    opciones.add_argument('--no-sandbox')
    
    # IMPORTANTE: Mantén tu ruta y versión fija que ya comprobamos que funciona
    ruta_navegador = r"C:\Users\USUARIO\AppData\Local\Thorium\Application\thorium.exe"
    
    try:
        driver = uc.Chrome(
            options=opciones, 
            browser_executable_path=ruta_navegador, 
            version_main=138
        )
    except Exception as e:
        print(f"Error fatal al iniciar el driver: {e}")
        return

    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    reanudar = (os.environ.get('SUPERFRESH_RESUME') == '1' and CSV_PATH.exists()
                and (CHECKPOINT.exists() or os.environ.get('SUPERFRESH_START_CATEGORY')))
    estado = json.loads(CHECKPOINT.read_text(encoding='utf-8')) if reanudar and CHECKPOINT.exists() else {
        'categoria': os.environ.get('SUPERFRESH_START_CATEGORY', categorias[0]), 'pagina': 1
    }
    skus_vistos = set()
    if reanudar:
        with CSV_PATH.open(newline='', encoding='utf-8') as entrada:
            for fila in csv.DictReader(entrada):
                skus_vistos.add(fila['sku_ean'] or fila['enlace'])
        print(f"Reanudando desde {estado}; {len(skus_vistos)} productos guardados")
    cabeceras = ['sku_ean', 'nombre', 'categoria', 'precio_base_ref', 'precio_final_ref', 'estado_iva', 'imagen', 'enlace']

    with CSV_PATH.open(mode='a' if reanudar else 'w', newline='', encoding='utf-8') as archivo:
        writer = csv.DictWriter(archivo, fieldnames=cabeceras)
        if not reanudar:
            writer.writeheader()

        for cat in categorias:
            if categorias.index(cat) < categorias.index(estado['categoria']):
                continue
            pagina = estado['pagina'] if cat == estado['categoria'] else 1
            print(f"\n--- Iniciando Categoría: {cat.upper()} ---")

            while True:
                # Rutas de WooCommerce
                url = f"{base_url}{cat}/" if pagina == 1 else f"{base_url}{cat}/page/{pagina}/"
                print(f"Scrapeando [{cat}] - Página {pagina}...")
                
                driver.get(url)
                
                # Le damos 5 segundos al navegador para renderizar la página y engañar al firewall
                time.sleep(5)
                
                html = driver.page_source
                soup = BeautifulSoup(html, 'html.parser')
                if any(marca in html.lower() for marca in ('cf-challenge', 'just a moment...', 'attention required!')):
                    raise RuntimeError(f'Página de protección en {url}; se conserva el avance')
                
                tarjetas = soup.find_all('li', class_='type-product')
                
                # Si no encontramos tarjetas, significa que llegamos al final de la categoría
                if not tarjetas:
                    print(f"Fin de la categoría '{cat}'. Avanzando a la siguiente...")
                    siguiente = categorias.index(cat) + 1
                    if siguiente < len(categorias):
                        CHECKPOINT.write_text(json.dumps({'categoria': categorias[siguiente], 'pagina': 1}), encoding='utf-8')
                    break

                datos_pagina = []

                for tarjeta in tarjetas:
                    # Extracción del EAN / Código de barras nativo
                    btn_carrito = tarjeta.find('a', class_='add_to_cart_button')
                    sku_ean = btn_carrito.get('data-product_sku', '') if btn_carrito else ''
                    id_producto = btn_carrito.get('data-product_id', '') if btn_carrito else ''

                    nodo_enlace = tarjeta.find('a', class_='woocommerce-LoopProduct-link')
                    enlace = nodo_enlace.get('href', '') if nodo_enlace else ''
                    id_unico = sku_ean or enlace or id_producto

                    # Escudo anti-duplicados entre categorías
                    if not id_unico or id_unico in skus_vistos:
                        continue
                        
                    skus_vistos.add(id_unico)

                    nodo_titulo = tarjeta.find('h2', class_='woocommerce-loop-product__title')
                    nombre = nodo_titulo.text.strip() if nodo_titulo else 'Sin nombre'

                    nodo_img = tarjeta.find('img', class_='attachment-woocommerce_thumbnail')
                    imagen = nodo_img.get('src', '') if nodo_img else ''

                    nodo_precio = tarjeta.find('span', class_='woocommerce-Price-amount')
                    precio_final = 0.0
                    
                    if nodo_precio:
                        # Limpieza matemática
                        precio_texto = nodo_precio.text.replace('$', '').replace(',', '.').strip()
                        try:
                            precio_final = float(precio_texto)
                            
                        except ValueError:
                            pass

                    datos_pagina.append({
                        'sku_ean': sku_ean,
                        'nombre': nombre,
                        'categoria': cat,
                        'precio_base_ref': None,
                        'precio_final_ref': precio_final,
                        'estado_iva': 'no_informado',
                        'imagen': imagen,
                        'enlace': enlace
                    })

                # Guardado en tiempo real al disco duro
                if datos_pagina:
                    writer.writerows(datos_pagina)
                    archivo.flush()

                pagina += 1
                CHECKPOINT.write_text(json.dumps({'categoria': cat, 'pagina': pagina}), encoding='utf-8')

    # Cerramos el navegador para liberar la memoria RAM
    print(f"\nExtracción finalizada exitosamente. {len(skus_vistos)} productos únicos guardados.")
    driver.quit()
    CHECKPOINT.unlink(missing_ok=True)

if __name__ == "__main__":
    scrapear_super_fresh_market()
