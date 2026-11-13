import requests
import csv
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def configurar_sesion_robusta():
    session = requests.Session()
    estrategia_reintentos = Retry(
        total=5, 
        backoff_factor=1, 
        status_forcelist=[429, 500, 502, 503, 504], 
        allowed_methods=["GET"]
    )
    session.mount("https://", HTTPAdapter(max_retries=estrategia_reintentos))
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    return session

def extraer_categoria(url_base, session):
    # Extraemos el nombre de la categoría desde la URL y lo limpiamos
    categoria_nombre = url_base.split('/')[-1].replace('-', ' ').title()
    print(f"\nIniciando extracción para: {categoria_nombre}")
    
    url_pag_1 = f"{url_base}?pag=1"
    
    try:
        response = session.get(url_pag_1, timeout=15)
    except Exception as e:
        print(f"❌ Error crítico de red al iniciar la categoría: {e}")
        return []
        
    if response.status_code != 200:
        print(f"❌ Error al conectar con la API. Código de estado: {response.status_code}")
        return []
        
    datos = response.json()
    
    try:
        max_paginas = datos['producto']['maxpag']
        productos_pag_1 = datos['producto']['data']
    except KeyError:
        print("❌ Error: La estructura del JSON no es la esperada.")
        return []

    print(f"✅ Se detectaron {max_paginas} páginas en total para esta categoría.")
    
    productos_categoria = []
    
    for item in productos_pag_1:
        procesar_item(item, productos_categoria, categoria_nombre)
        
    print(f"Página 1 procesada. Extraídos {len(productos_pag_1)} productos.")
    
    for pagina in range(2, max_paginas + 1):
        url_actual = f"{url_base}?pag={pagina}"
        try:
            res = session.get(url_actual, timeout=15)
            if res.status_code == 200:
                datos_pag = res.json()
                productos_actuales = datos_pag.get('producto', {}).get('data', [])
                
                for item in productos_actuales:
                    procesar_item(item, productos_categoria, categoria_nombre)
                    
                print(f"Página {pagina}/{max_paginas} procesada. Extraídos {len(productos_actuales)} productos.")
            else:
                print(f"⚠️ Error en la página {pagina}. Código: {res.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"⚠️ La conexión se reinició en la página {pagina} incluso tras los reintentos. Saltando.")
        except requests.exceptions.Timeout:
            print(f"⚠️ Timeout en la página {pagina}. El servidor tardó demasiado en responder. Saltando.")
        except Exception as e:
            print(f"⚠️ Excepción inesperada en la página {pagina}: {e}")
            
        time.sleep(0.5)

    return productos_categoria

def procesar_item(item, lista_destino, categoria):
    sku = item.get('sku', 'Sin SKU')
    nombre = item.get('nombre', 'Sin Nombre')
    
    precio_base_ref = None
    precio_ref_final = None
    
    precios_lista = item.get('precio', [])
    
    precio_basico = None
    info_impuesto = None
    
    for p in precios_lista:
        tipo_usuario = p.get('usuarioTipo', {}).get('nombre', '')
        if tipo_usuario.lower() == 'basico':
            precio_basico = p.get('precio', 0) / 100.0  
            info_impuesto = p.get('impuesto', {})
            break
            
    if precio_basico is None and precios_lista:
        p = precios_lista[0]
        precio_basico = p.get('precio', 0) / 100.0
        info_impuesto = p.get('impuesto', {})
        
    if precio_basico:
        porcentaje_impuesto = info_impuesto.get('porcentaje', 0)
        
        if porcentaje_impuesto > 0:
            precio_base_ref = precio_basico
            multiplicador = 1 + (porcentaje_impuesto / 10000.0)
            precio_ref_final = round(precio_basico * multiplicador, 2)
        else:
            precio_base_ref = precio_basico
            precio_ref_final = precio_basico

    lista_destino.append({
        'categoria': categoria,
        'sku': sku,
        'nombre': nombre,
        'precio_base_ref': precio_base_ref,
        'precio_ref_final': precio_ref_final
    })

if __name__ == "__main__":
    urls_categorias = [
        "https://api.tuzonamarket.com/api/categoria/supermercado/2/alimentos",
        "https://api.tuzonamarket.com/api/categoria/supermercado/2/carniceria-y-pescaderia",
        "https://api.tuzonamarket.com/api/categoria/supermercado/2/farmacia",
        "https://api.tuzonamarket.com/api/categoria/supermercado/2/limpieza-y-hogar",
        "https://api.tuzonamarket.com/api/categoria/supermercado/2/licoreria",
        "https://api.tuzonamarket.com/api/categoria/supermercado/2/bebidas",
        "https://api.tuzonamarket.com/api/categoria/supermercado/2/cuidado-personal",
        "https://api.tuzonamarket.com/api/categoria/supermercado/2/congelados-y-refrigerados",
        "https://api.tuzonamarket.com/api/categoria/supermercado/2/helados-y-postres",
        "https://api.tuzonamarket.com/api/categoria/supermercado/2/bebes",
        "https://api.tuzonamarket.com/api/categoria/supermercado/2/panaderia-pasteleria-y-charcuteria",
        "https://api.tuzonamarket.com/api/categoria/supermercado/2/cigarros",
        "https://api.tuzonamarket.com/api/categoria/supermercado/2/saludable",
        "https://api.tuzonamarket.com/api/categoria/supermercado/2/delicatessen",
        "https://api.tuzonamarket.com/api/categoria/supermercado/2/navidad",
        "https://api.tuzonamarket.com/api/categoria/supermercado/2/bodegon-italiano"
    ]

    todos_los_productos = []
    nombre_archivo_salida = "productos_tuzonamarket_completo.csv"
    
    sesion_global = configurar_sesion_robusta()

    for url in urls_categorias:
        productos = extraer_categoria(url, sesion_global)
        todos_los_productos.extend(productos)
        time.sleep(1)

    print(f"\nGuardando {len(todos_los_productos)} productos en total...")
    
    with open(nombre_archivo_salida, mode='w', newline='', encoding='utf-8') as archivo_csv:
        cabeceras = ['categoria', 'sku', 'nombre', 'precio_base_ref', 'precio_ref_final']
        writer = csv.DictWriter(archivo_csv, fieldnames=cabeceras)
        writer.writeheader()
        writer.writerows(todos_los_productos)
        
    print(f"🎉 ¡Extracción total completada! Archivo generado: '{nombre_archivo_salida}'")