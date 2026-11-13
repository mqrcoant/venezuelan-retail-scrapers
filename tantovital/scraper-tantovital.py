from bs4 import BeautifulSoup
import pandas as pd
import re
import requests
import time
from urllib.parse import urljoin

BASE_URL = "https://www.tantovital.com"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# ==========================================
# CONFIGURACIÓN: Elige la cadena a extraer
# Opciones válidas: "FarmaGO", "Cristalmed", "Enviamed", "Farmacia Beca"
# ==========================================
CADENA_A_EXTRAER = "Farmacia Beca"  # Cambia esto según la cadena que quieras scrapear

def obtener_sucursales_por_cadena(cadena_objetivo, session):
    """Extrae la timeline y filtra solo las sucursales de la cadena seleccionada."""
    print(f"\n[*] Buscando sucursales de la cadena: {cadena_objetivo}...")
    url_timeline = f"{BASE_URL}/Farmacias/Index"
    
    res = session.get(url_timeline)
    soup = BeautifulSoup(res.text, 'html.parser')
    nodos = soup.find_all('div', class_=re.compile(r'timeline-nodes'))
    
    sucursales = {}
    for nodo in nodos:
        btn = nodo.find('a', class_='tanto-btn', href=re.compile(r'farmacia='))
        if not btn: continue
            
        href = btn.get('href')
        match = re.search(r'farmacia=([^&]+)', href)
        if match:
            farmacia_id = match.group(1)
            nombre = nodo.find('h3').text.strip() if nodo.find('h3') else farmacia_id
            
            # Filtrado por cadena
            id_lower = farmacia_id.lower()
            pertenece = False
            
            if cadena_objetivo == "FarmaGO" and 'farmago' in id_lower: pertenece = True
            elif cadena_objetivo == "Cristalmed" and 'cristalmed' in id_lower: pertenece = True
            elif cadena_objetivo == "Enviamed" and 'enviamed' in id_lower: pertenece = True
            elif cadena_objetivo == "Farmacia Beca" and 'beca' in id_lower: pertenece = True
                
            if pertenece:
                sucursales[farmacia_id] = nombre
                
    print(f"[+] Se encontraron {len(sucursales)} sucursales para {cadena_objetivo}.")
    return sucursales

def obtener_max_paginas(farmacia_id, session):
    url = f"{BASE_URL}/Farmacias/Productos?farmacia={farmacia_id}&page=1"
    res = session.get(url)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    max_page = 1
    btn_last = soup.find('a', attrs={'aria-label': 'Last'})
    if btn_last:
        match = re.search(r'page=(\d+)', btn_last.get('href', ''))
        if match: return int(match.group(1))
        
    links = soup.find_all('a', class_='page-link', href=re.compile(r'page=\d+'))
    for link in links:
        match = re.search(r'page=(\d+)', link.get('href', ''))
        if match: max_page = max(max_page, int(match.group(1)))
            
    return max_page

def extraer_ean_ficha(url_producto, session):
    """Visita la ficha individual del producto y extrae el EAN del texto descriptivo"""
    try:
        res = session.get(url_producto, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            # Buscamos todos los spans con la clase indicada
            spans = soup.find_all('span', class_='text-coolgray')
            for span in spans:
                texto = span.get_text()
                if 'Código EAN:' in texto:
                    match = re.search(r'Código EAN:\s*(\d+)', texto)
                    if match:
                        return match.group(1)
    except Exception:
        pass
    return "N/A"

def scrape_cadena():
    # Inicializamos una Sesión para reutilizar la conexión y ganar muchísima velocidad
    session = requests.Session()
    session.headers.update(HEADERS)
    
    sucursales = obtener_sucursales_por_cadena(CADENA_A_EXTRAER, session)
    if not sucursales:
        print("[!] No se encontraron sucursales. Revisa la conexión o el nombre de la cadena.")
        return

    diccionario_productos = {}

    for farmacia_id, nombre_sucursal in sucursales.items():
        max_pages = obtener_max_paginas(farmacia_id, session)
        print(f"\n  -> Procesando {nombre_sucursal} ({max_pages} páginas)...")
        
        for page in range(1, max_pages + 1):
            url = f"{BASE_URL}/Farmacias/Productos?farmacia={farmacia_id}&PrecioMinimo=0&PrecioMaximo=100000&page={page}"
            
            exito = False
            for intento in range(3):
                try:
                    res = session.get(url, timeout=15)
                    if res.status_code == 200:
                        soup = BeautifulSoup(res.text, 'html.parser')
                        tarjetas = soup.find_all('div', class_=lambda c: c and 'card' in c and 'text-center' in c)
                        
                        for tarjeta in tarjetas:
                            nombre = "N/A"
                            enlace_producto = None
                            
                            label = tarjeta.find('label', class_='form-check-label')
                            if label and label.find('a'): 
                                a_tag = label.find('a')
                                nombre = a_tag.text.strip()
                                enlace_producto = urljoin(BASE_URL, a_tag.get('href'))
                            
                            precio = None
                            precio_tag = tarjeta.find('div', class_='product-price')
                            if precio_tag and precio_tag.find('strong'):
                                try: precio = float(precio_tag.find('strong').text.replace('USD', '').strip())
                                except ValueError: pass
                                
                            imagen_url, barcode_img = "N/A", "N/A"
                            img = tarjeta.find('img')
                            if img:
                                src = img.get('src', '')
                                imagen_url = urljoin(BASE_URL, src)
                                # Capturamos el de la imagen por si la ficha falla
                                match_bc = re.search(r'/([^/]+)\.(webp|jpg|png|jpeg)$', src, re.IGNORECASE)
                                if match_bc and match_bc.group(1).isdigit(): 
                                    barcode_img = match_bc.group(1)
                                
                            if nombre != "N/A":
                                # Extracción del EAN real entrando a la ficha
                                ean_real = "N/A"
                                if enlace_producto:
                                    ean_real = extraer_ean_ficha(enlace_producto, session)
                                    time.sleep(0.05) # Micro-pausa para simular fluidez humana
                                
                                # Prevalece el de la ficha, sino usa el de la imagen
                                barcode_final = ean_real if ean_real != "N/A" else barcode_img
                                
                                llave = (barcode_final, nombre)
                                if llave not in diccionario_productos:
                                    diccionario_productos[llave] = {
                                        'SKU / Barcode': barcode_final,
                                        'Nombre': nombre,
                                        'Precio Final REF': precio,
                                        'Imagen URL': imagen_url,
                                        'Sucursales Disponibles': [nombre_sucursal]
                                    }
                                else:
                                    if nombre_sucursal not in diccionario_productos[llave]['Sucursales Disponibles']:
                                        diccionario_productos[llave]['Sucursales Disponibles'].append(nombre_sucursal)
                        
                        exito = True
                        break # Salir del loop de reintentos
                    else:
                        print(f"     [!] Bloqueo en pág {page}. Pausa 3s...")
                        time.sleep(3)
                except Exception:
                    time.sleep(3)
            
            if not exito:
                print(f"     [X] Pág {page} saltada tras 3 fallos.")
            else:
                print(f"     - Pág {page}/{max_pages} procesada con éxito.")
                
            time.sleep(0.5) # Pausa entre páginas del catálogo

    # Exportación final
    lista_final = []
    for prod in diccionario_productos.values():
        prod['Sucursales Disponibles'] = ", ".join(prod['Sucursales Disponibles'])
        # Quitar columna si no es cadena multi-sucursal
        if CADENA_A_EXTRAER not in ["Enviamed", "Farmacia Beca"]:
            del prod['Sucursales Disponibles']
        lista_final.append(prod)

    if lista_final:
        df = pd.DataFrame(lista_final)
        nombre_arch = f"tantovital_{CADENA_A_EXTRAER.lower().replace(' ', '_')}.xlsx"
        df.to_excel(nombre_arch, index=False)
        print(f"\n[+] Éxito total. {len(lista_final)} productos consolidados y guardados en {nombre_arch}")
    else:
        print("\n[-] No se extrajeron productos.")

if __name__ == "__main__":
    scrape_cadena()