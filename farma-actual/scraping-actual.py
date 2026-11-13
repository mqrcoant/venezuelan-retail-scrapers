import requests
from bs4 import BeautifulSoup
import csv
import time
import os

def scrapear_farmacia_actual():
    while True:
        tasa_input = (os.environ.get("BCV_RATE") or input("Ingresa la tasa BCV de hoy: ")).strip().replace(',', '.')
        try:
            tasa_bcv = float(tasa_input)
            if tasa_bcv > 0:
                print(f"Tasa fijada en: {tasa_bcv} Bs/USD. Iniciando extracción...\n")
                break
            if os.environ.get("BCV_RATE"):
                raise SystemExit("BCV_RATE debe ser positiva")
            print("Error: La tasa debe ser mayor a 0.")
        except ValueError:
            if os.environ.get("BCV_RATE"):
                raise SystemExit("BCV_RATE inválida")
            print("Error: Formato numérico inválido.")

    base_url = "https://www.tufarmaciaactual.com/shop/page/"
    dominio = "https://www.tufarmaciaactual.com"
    pagina = 1
    productos_extraidos = []
    
    # Escudo para evitar el bucle infinito de Odoo
    skus_vistos = set()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'X-Requested-With': 'XMLHttpRequest'
    }

    while True:
        print(f"Extrayendo página {pagina}...")
        url = f"{base_url}{pagina}"
        res = requests.get(url, headers=headers, timeout=20)
        
        if res.status_code != 200:
            print("Límite de ruta alcanzado.")
            break
            
        soup = BeautifulSoup(res.text, 'html.parser')
        tarjetas = soup.find_all('div', class_='tp-product-item')
        
        if not tarjetas:
            break

        productos_nuevos_en_pagina = 0

        for tarjeta in tarjetas:
            nodo_id = tarjeta.find('input', {'name': 'product_id'})
            sku_interno = nodo_id['value'] if nodo_id else ''

            if not sku_interno or sku_interno in skus_vistos:
                continue
                
            skus_vistos.add(sku_interno)
            productos_nuevos_en_pagina += 1

            nodo_enlace = tarjeta.find('a', itemprop='name')
            nombre = nodo_enlace.text.strip() if nodo_enlace else 'Sin nombre'
            enlace = f"{dominio}{nodo_enlace['href']}" if nodo_enlace and 'href' in nodo_enlace.attrs else ''
            
            nodo_img = tarjeta.find('img', class_='tp-product-image')
            imagen = f"{dominio}{nodo_img['src']}" if nodo_img and 'src' in nodo_img.attrs else ''
            
            nodo_precio = tarjeta.find('span', class_='oe_currency_value')
            precio_bs = 0.0
            precio_ref = 0.0
            
            if nodo_precio:
                precio_texto = nodo_precio.text.strip().replace('.', '').replace(',', '.')
                try:
                    precio_bs = float(precio_texto)
                    precio_ref = round(precio_bs / tasa_bcv, 2)
                except ValueError:
                    pass

            productos_extraidos.append({
                'sku_interno': sku_interno,
                'nombre': nombre,
                'precio_bs': precio_bs,
                'precio_ref': precio_ref,
                'imagen': imagen,
                'enlace': enlace
            })

        if productos_nuevos_en_pagina == 0:
            print(f"Odoo empezó a repetir productos en la pág {pagina}. Fin real alcanzado.")
            break

        pagina += 1
        time.sleep(0.5)

    if productos_extraidos:
        cabeceras = ['sku_interno', 'nombre', 'precio_bs', 'precio_ref', 'imagen', 'enlace']
        with open('maestro_tu_farmacia_actual.csv', mode='w', newline='', encoding='utf-8') as archivo:
            writer = csv.DictWriter(archivo, fieldnames=cabeceras)
            writer.writeheader()
            writer.writerows(productos_extraidos)
        print(f"\nExtracción finalizada. {len(productos_extraidos)} productos únicos guardados.")

if __name__ == "__main__":
    scrapear_farmacia_actual()
