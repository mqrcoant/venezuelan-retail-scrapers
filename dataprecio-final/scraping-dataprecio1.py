from playwright.sync_api import sync_playwright
import urllib.parse
import pandas as pd
import time
import random
import re

TIENDAS = [
    "Central Madeirense", "Farmatodo", "Kalea", "Luvebras", "Gama", 
    "Locatel", "Plansuarez", "Plazas", "Forum", "Unicasa", 
    "Automercados Emporium", "Celicor Boutique", "Viva Supercentro", 
    "Ferreterias Epa", "Licores Mundiales", "Automercado Santa Paula", "Rio Vida"
]

def extraer_tienda(context, nombre_tienda):
    datos_tienda = []
    tienda_encoded = urllib.parse.quote_plus(nombre_tienda)
    url_tienda = f"https://www.dataprecio.com/?store={tienda_encoded}"
    
    page = context.new_page()
    
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        window.__playwright = undefined;
        window.__pwInitScripts = undefined;
        window.__pw_manual = undefined;
    """)
    
    print(f"\n[*] Iniciando tienda: {nombre_tienda}")
    
    try:
        page.goto(url_tienda)
        page.wait_for_selector(".product", timeout=20000)
        time.sleep(2)
    except Exception as e:
        print(f"[!] Error al cargar los productos de la tienda: {e}")
        page.close()
        return []

    # ==========================================
    # 1. EXTRAER EL NÚMERO TOTAL DE PÁGINAS
    # ==========================================
    total_paginas = 1
    try:
        texto_resumen = page.locator(".search-results-summary").inner_text(timeout=5000)
        match = re.search(r"de (\d+)\)", texto_resumen)
        if match:
            total_paginas = int(match.group(1))
            print(f"[+] Se detectaron {total_paginas} páginas a procesar.")
    except Exception:
        print("[!] No se detectó la paginación, se asume 1 página.")

    # ==========================================
    # 2. BUCLE FOR SEGURO
    # ==========================================
    selector_tarjeta = ".product"
    
    for pagina_actual in range(1, total_paginas + 1):
        print(f"  - Extrayendo página {pagina_actual} de {total_paginas}...")
        
        tarjetas = page.locator(selector_tarjeta).all()
        
        for tarjeta in tarjetas:
            id_producto = tarjeta.get_attribute("data-product-id") or "N/A"
            try:
                nombre = tarjeta.locator(".product-title-container h2").inner_text(timeout=1000).strip()
            except:
                nombre = "Desconocido"
            
            cajas_tienda = tarjeta.locator(".stores li").all()
            for caja in cajas_tienda:
                tienda_actual = caja.get_attribute("data-store-name")
                nodo_precio = caja.locator(".price")
                precio_limpio = nodo_precio.get_attribute("data-base-price") if nodo_precio.count() > 0 else None
                
                nodo_metrica = caja.locator(".store-price-per-unit")
                metrica = nodo_metrica.inner_text().strip() if nodo_metrica.count() > 0 else "N/A"
                
                if tienda_actual and precio_limpio:
                    datos_tienda.append({
                        "ID_Dataprecio": id_producto,
                        "Nombre": nombre,
                        "Tienda": tienda_actual.strip(),
                        "Precio_USD": float(precio_limpio),
                        "Metrica": metrica
                    })
        
        # ==========================================
        # 3. NAVEGACIÓN CON REINTENTOS (EXPONENTIAL BACKOFF)
        # ==========================================
        if pagina_actual < total_paginas:
            boton_siguiente = page.locator("#pagination-controls button:last-child")
            texto_esperado = f"página {pagina_actual + 1} de {total_paginas}"
            
            max_intentos = 3
            intento_actual = 0
            exito_paginacion = False
            
            while intento_actual < max_intentos and not exito_paginacion:
                try:
                    # 1. Aseguramos que el botón exista
                    boton_siguiente.wait_for(state="attached", timeout=10000)
                    boton_siguiente.evaluate("el => el.click()")
                    
                    # 2. Esperamos a que el texto cambie
                    page.wait_for_function(
                        f"() => document.querySelector('.search-results-summary') && document.querySelector('.search-results-summary').innerText.includes('{texto_esperado}')", 
                        timeout=20000 
                    )
                    
                    # Si llegamos aquí, la página cargó bien
                    exito_paginacion = True
                    time.sleep(random.uniform(2.5, 4.5))
                    
                except Exception as e:
                    intento_actual += 1
                    tiempo_espera = 15 * intento_actual # Pausa progresiva: 15s, 30s, 45s
                    print(f"    [!] Atasco en página {pagina_actual + 1} (Intento {intento_actual}/{max_intentos}). Servidor ocupado.")
                    
                    if intento_actual < max_intentos:
                        print(f"    [*] Aplicando backoff... esperando {tiempo_espera} segundos antes de reintentar.")
                        time.sleep(tiempo_espera)
                    else:
                        print(f"[!] Agotados los 3 reintentos para la página {pagina_actual + 1}. Guardando progreso parcial...")
            
            # Si después de 3 intentos falló, entonces sí rompemos el ciclo de esta tienda
            if not exito_paginacion:
                break

    page.close()
    return datos_tienda

def main():
    catalogo_total = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False, # Mantenlo en False para evadir las defensas
            args=["--disable-blink-features=AutomationControlled"]
        ) 
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768}
        )
        
        for tienda in TIENDAS: 
            resultados = extraer_tienda(context, tienda)
            catalogo_total.extend(resultados)
            
            # Pausa táctica al cambiar de tienda
            time.sleep(random.uniform(4, 8)) 
            
        browser.close()
        
    if catalogo_total:
        df = pd.DataFrame(catalogo_total)
        df.drop_duplicates(subset=["ID_Dataprecio", "Tienda"], inplace=True)
        
        fecha_str = time.strftime("%Y%m%d_%H%M")
        archivo_salida = f"catalogo_maestro_dataprecio_{fecha_str}.csv"
        df.to_csv(archivo_salida, index=False, encoding='utf-8')
        
        print(f"\n[+] ¡Éxito! CSV guardado con {len(df)} registros en '{archivo_salida}'.")
    else:
        print("\n[-] La extracción falló o no obtuvo datos.")

if __name__ == "__main__":
    main()