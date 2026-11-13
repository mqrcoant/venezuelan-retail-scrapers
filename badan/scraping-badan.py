import requests
from bs4 import BeautifulSoup
import csv
import time
import concurrent.futures

def extraer_catalogo_badan():
    base_url = "https://farmaciabadan.com/medicamentos?p="
    pagina_actual = 1
    productos_extraidos = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    print("Iniciando escaneo del catálogo maestro con Multi-threading...")

    while True:
        print(f"Scrapeando página {pagina_actual}...")
        url = f"{base_url}{pagina_actual}"
        respuesta = requests.get(url, headers=headers)
        
        if respuesta.status_code != 200:
            print(f"Error o fin de páginas en la pag {pagina_actual}.")
            break
            
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        tarjetas = soup.find_all('li', class_='item product product-item')
        
        if not tarjetas:
            print("No se encontraron más productos. Finalizando barrido.")
            break

        # Función aislada para procesar cada tarjeta de forma independiente
        def extraer_detalles_producto(tarjeta):
            # 1. Datos base de la cuadrícula
            nodo_enlace = tarjeta.find('a', class_='product-item-link')
            if not nodo_enlace:
                return None
                
            nombre = nodo_enlace.text.strip()
            link_producto = nodo_enlace.get('href')
            
            nodo_precio = tarjeta.find('span', class_='price-wrapper')
            precio = float(nodo_precio.get('data-price-amount', 0)) if nodo_precio else 0.0
            
            nodo_id = tarjeta.find('div', class_='price-box')
            id_interno = nodo_id.get('data-product-id', '') if nodo_id else ''
            
            nodo_origen = tarjeta.find('div', class_='country')
            origen = nodo_origen.text.strip() if nodo_origen else 'N/A'
            
            nodo_img = tarjeta.find('img', class_='product-image-photo')
            imagen = nodo_img.get('src', '') if nodo_img else ''

            # 2. Extracción profunda del EAN (Operación pesada de red)
            ean_oculto = ''
            sku_oculto = ''
            try:
                res_prod = requests.get(link_producto, headers=headers, timeout=10)
                soup_prod = BeautifulSoup(res_prod.text, 'html.parser')
                scripts_ld = soup_prod.find_all('script', type='application/ld+json')
                
                for script in scripts_ld:
                    if 'Product' in script.text:
                        import json
                        data_ld = json.loads(script.text)
                        ean_oculto = data_ld.get('gtin13', data_ld.get('gtin8', data_ld.get('gtin', '')))
                        sku_oculto = data_ld.get('sku', '')
                        break
            except Exception:
                pass 

            return {
                'id_badan': id_interno,
                'sku_vtex_ean': ean_oculto if ean_oculto else sku_oculto,
                'nombre': nombre,
                'marca_origen': origen,
                'precio_base': precio,
                'imagen': imagen,
                'url': link_producto
            }

        # Ejecutamos las peticiones en paralelo con 5 trabajadores (hilos)
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            resultados = executor.map(extraer_detalles_producto, tarjetas)
            
            for item in resultados:
                if item:
                    productos_extraidos.append(item)
            
        pagina_actual += 1

    # 3. Guardado del Maestro
    if productos_extraidos:
        cabeceras = ['id_badan', 'sku_vtex_ean', 'nombre', 'marca_origen', 'precio_base', 'imagen', 'url']
        with open('maestro_badan_optimizado.csv', mode='w', newline='', encoding='utf-8') as archivo:
            writer = csv.DictWriter(archivo, fieldnames=cabeceras)
            writer.writeheader()
            writer.writerows(productos_extraidos)
        print(f"Éxito: {len(productos_extraidos)} productos guardados en maestro_badan_optimizado.csv")

if __name__ == "__main__":
    extraer_catalogo_badan()