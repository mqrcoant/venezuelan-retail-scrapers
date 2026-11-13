import requests
from bs4 import BeautifulSoup
import csv
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SEDES_DISPONIBLES = [
    "https://higuerote.elplazas.com/",
    "https://buenaventura.elplazas.com/",
    "https://avila.elplazas.com/",
    "https://lagunita.elplazas.com/",
    "https://cafetal.elplazas.com/",
    "https://naranjos.elplazas.com/",
    "https://santaeduvigis.elplazas.com/",
    "https://centroplaza.elplazas.com/",
    "https://samanes.elplazas.com/",
    "https://vallearriba.elplazas.com/",
    "https://cedros.elplazas.com/",
    "https://galerias.elplazas.com/",
    "https://chaguaramos.elplazas.com/",
    "https://prado.elplazas.com/",
    "https://sanbernardino.elplazas.com/",
    "https://paraiso.elplazas.com/",
    "https://vistaalegre.elplazas.com/",
    "https://sanantonio.elplazas.com/"
]

def configurar_sesion_robusta():
    session = requests.Session()
    estrategia_reintentos = Retry(
        total=5, 
        backoff_factor=1,  
        status_forcelist=[429, 500, 502, 503, 504], 
        allowed_methods=["GET", "POST"]
    )
    session.mount("https://", HTTPAdapter(max_retries=estrategia_reintentos))
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    return session

def iniciar_sesion_magento(url_base, email, password, session):
    print(f"  -> Autenticando usuario en {url_base}...")
    url_login_get = f"{url_base}customer/account/login/"
    url_login_post = f"{url_base}customer/account/loginPost/"
    
    try:
        respuesta_get = session.get(url_login_get, timeout=15)
        soup = BeautifulSoup(respuesta_get.text, 'html.parser')
        
        input_form_key = soup.select_one('input[name="form_key"]')
        if not input_form_key:
            print("  [!] No se pudo encontrar el form_key para el login.")
            return False
            
        form_key = input_form_key['value']
        
        payload_login = {
            'form_key': form_key,
            'login[username]': email,
            'login[password]': password,
            'send': ''
        }
        
        respuesta_post = session.post(url_login_post, data=payload_login, timeout=15)
        
        if "customer/account" in respuesta_post.url or "Olvido su contraseña" not in respuesta_post.text:
            print("  [+] ¡Sesión iniciada correctamente!")
            return True
        else:
            print("  [-] Fallo el inicio de sesión. Verifica credenciales.")
            return False
            
    except Exception as e:
        print(f"  [!] Error durante el login: {e}")
        return False

def obtener_categorias(url_sede, session):
    print(f"\nObteniendo categorías principales de {url_sede}...")
    try:
        respuesta = session.get(url_sede, timeout=15)
    except Exception as e:
        print(f"Error crítico al acceder a la página principal: {e}")
        return []
    
    if respuesta.status_code != 200:
        return []

    soup = BeautifulSoup(respuesta.text, 'html.parser')
    categorias = []
    urls_vistas = set() 
    
    enlaces_cat = soup.select('li.level0 > a')
    
    for a in enlaces_cat:
        url = a.get('href')
        texto_bruto = a.text.strip()
        nombre_cat = texto_bruto.split('(')[0].strip() if '(' in texto_bruto else texto_bruto
        
        if url and url not in urls_vistas:
            urls_vistas.add(url)
            categorias.append({
                'nombre': nombre_cat,
                'url': url
            })
            
    return categorias

def scrapear_categoria(url_base, nombre_categoria, nombre_sede, productos_dict, session, nombre_archivo):
    pagina_actual = 1

    while True:
        print(f"  -> Scrapeando [{nombre_categoria}] - página {pagina_actual}...")
        url_paginada = f"{url_base}?p={pagina_actual}"
        
        time.sleep(1) 
        
        try:
            respuesta = session.get(url_paginada, timeout=15)
        except Exception as e:
            print(f"  [!] Error de conexión en la página {pagina_actual}: {e}")
            break
            
        if respuesta.status_code != 200:
            break

        soup = BeautifulSoup(respuesta.text, 'html.parser')
        productos = soup.select('li.product-item')
        
        if not productos:
            break
            
        input_form_key_global = soup.select_one('input[name="form_key"]')
        form_key_global = input_form_key_global['value'] if input_form_key_global else None
        dominio_base = f"{url_base.split('/')[0]}//{url_base.split('/')[2]}/"

        for prod in productos:
            elem_form = prod.select_one('form[data-product-sku]')
            sku = elem_form['data-product-sku'] if elem_form else None
            
            if not sku:
                continue
                
            # 1. Comprobación en memoria mejorada
            if sku in productos_dict:
                # Agregamos la sede actual a la disponibilidad
                if nombre_sede not in productos_dict[sku]['tiendas_disponibles']:
                    productos_dict[sku]['tiendas_disponibles'].append(nombre_sede)
                
                # Si ya logramos capturar el precio sin IVA anteriormente, evitamos el carrito y saltamos
                if productos_dict[sku].get('precio_sin_iva') is not None:
                    continue
                # Si el precio_sin_iva es None, NO hacemos continue. 
                # Dejamos que el script intente meterlo al carrito en esta nueva sede.
                
            # 2. Extracción de datos públicos
            elem_nombre = prod.select_one('.product-item-name a')
            nombre = elem_nombre.text.strip() if elem_nombre else None
            
            elem_precio = prod.select_one('[data-price-amount]')
            precio_bruto = float(elem_precio['data-price-amount']) if elem_precio else None
            precio_ref_final = round(precio_bruto, 2) if precio_bruto is not None else None
            
            elem_img = prod.select_one('.product-image-photo')
            img_url = elem_img['src'] if elem_img else None
            
            # 3. Extracción del precio sin IVA interactuando con el carrito loggeado
            precio_sin_iva = None
            if elem_form and form_key_global:
                action_url = elem_form.get('action')
                input_product = elem_form.select_one('input[name="product"]')
                
                if action_url and input_product:
                    product_id = input_product['value']
                    
                    payload = {
                        'product': product_id,
                        'selected_configurable_option': '',
                        'related_product': '',
                        'item': product_id,
                        'form_key': form_key_global,
                        'qty': '1'
                    }
                    
                    headers_ajax = {
                        'X-Requested-With': 'XMLHttpRequest',
                        'Referer': url_paginada
                    }
                    
                    try:
                        session.post(action_url, data=payload, headers=headers_ajax, timeout=10)
                        
                        timestamp = int(time.time() * 1000)
                        url_json = f"{dominio_base}customer/section/load/?sections=cart&_={timestamp}"
                        resp_json = session.get(url_json, headers=headers_ajax, timeout=10).json()
                        
                        if 'cart' in resp_json and 'items' in resp_json['cart']:
                            for item in resp_json['cart']['items']:
                                if item.get('product_sku') == sku:
                                    precio_sin_iva = item.get('product_price_value')
                                    item_id_to_delete = item.get('item_id')
                                    
                                    if item_id_to_delete:
                                        url_delete = f"{dominio_base}checkout/cart/delete/"
                                        payload_delete = {
                                            'id': item_id_to_delete,
                                            'form_key': form_key_global
                                        }
                                        session.post(url_delete, data=payload_delete, headers=headers_ajax, timeout=10)
                                    break
                                    
                    except Exception as e:
                        print(f"    [!] Error al obtener precio sin IVA para {sku}: {e}")

            # 4. Guardar en el diccionario maestro
            # Preservamos las tiendas acumuladas si el producto ya existía
            tiendas_acumuladas = productos_dict[sku]['tiendas_disponibles'] if sku in productos_dict else [nombre_sede]
            
            productos_dict[sku] = {
                'categoria': nombre_categoria,
                'sku': sku,
                'nombre': nombre,
                'precio_ref_final': precio_ref_final,
                'precio_sin_iva': precio_sin_iva,
                'imagen': img_url,
                'tiendas_disponibles': tiendas_acumuladas
            }
        
        guardar_csv_maestro(productos_dict, nombre_archivo, silencioso=True)
            
        boton_siguiente = soup.select_one('.pages-item-next a.next')
        if not boton_siguiente:
            break
            
        pagina_actual += 1

def guardar_csv_maestro(productos_dict, nombre_archivo="maestro_elplazas.csv", silencioso=False):
    if not productos_dict:
        return

    cabeceras = ['categoria', 'sku', 'nombre', 'precio_ref_final', 'precio_sin_iva', 'imagen', 'tiendas_disponibles']
    
    with open(nombre_archivo, mode='w', newline='', encoding='utf-8') as archivo_csv:
        escritor = csv.DictWriter(archivo_csv, fieldnames=cabeceras)
        escritor.writeheader()
        
        for sku, datos in productos_dict.items():
            fila = datos.copy()
            fila['tiendas_disponibles'] = ", ".join([f"plazas {sede}" for sede in datos['tiendas_disponibles']])
            escritor.writerow(fila)
        
    if not silencioso:
        print(f"\n¡Se guardaron {len(productos_dict)} productos únicos en el archivo: {nombre_archivo}!")

if __name__ == "__main__":
    print("=== INICIANDO EXTRACCIÓN MASIVA EN TIEMPO REAL (18 SEDES) ===")
    
    ARCHIVO_MAESTRO = "maestro_elplazas.csv"
    import os
    MI_EMAIL = os.environ.get("PLAZA_EMAIL")
    MI_PASSWORD = os.environ.get("PLAZA_PASSWORD")
    if not MI_EMAIL or not MI_PASSWORD:
        raise SystemExit("Faltan PLAZA_EMAIL y PLAZA_PASSWORD; no se inicia el scraping")
    
    sesion_global = configurar_sesion_robusta()
    productos_dict = {}
    
    guardar_csv_maestro(productos_dict, ARCHIVO_MAESTRO, silencioso=True)
    
    for url_sede in SEDES_DISPONIBLES:
        nombre_sede = url_sede.split('//')[1].split('.')[0]
        print(f"\n--- Procesando Sede: {nombre_sede.upper()} ---")
        
        if not iniciar_sesion_magento(url_sede, MI_EMAIL, MI_PASSWORD, sesion_global):
            print("Saltando sede por fallo de autenticación...")
            continue
        
        lista_categorias = obtener_categorias(url_sede, sesion_global)
        if not lista_categorias:
            continue
            
        print(f"Se encontraron {len(lista_categorias)} categorías en plazas {nombre_sede}.\n")
        
        for cat in lista_categorias:
            scrapear_categoria(cat['url'], cat['nombre'], nombre_sede, productos_dict, sesion_global, ARCHIVO_MAESTRO)
            
    guardar_csv_maestro(productos_dict, ARCHIVO_MAESTRO, silencioso=False)
