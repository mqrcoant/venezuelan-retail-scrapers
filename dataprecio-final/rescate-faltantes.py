from playwright.sync_api import sync_playwright
import urllib.parse
import pandas as pd
import time
import random
import re

# Diccionario con las tiendas faltantes y la página exacta donde se interrumpieron
TIENDAS_RESCATE = {
    "Farmatodo": 49,
    "Luvebras": 4,
    "Gama": 6,
    "Plansuarez": 13,
    "Automercados Emporium": 6
}

def extraer_tienda_rescate(context, nombre_tienda, pagina_inicio):
    datos_tienda = []
    tienda_encoded = urllib.parse.quote_plus(nombre_tienda)
    
    # Intentamos inyectar el parámetro page en la URL
    url_tienda = f"https://www.dataprecio.com/?store={tienda_encoded}&page={pagina_inicio}"
    
    page = context.new_page()
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        window.__playwright = undefined;
        window.__pwInitScripts = undefined;
        window.__pw_manual = undefined;
    """)
    
    print(f"\n[*] Iniciando rescate de: {nombre_tienda} (Desde pág. {pagina_inicio})")
    
    try:
        page.goto(url_tienda)
        page.wait_for_selector(".product:not(.is-skeleton)", timeout=20000)
        time.sleep(3)
    except Exception as e:
        print(f"[!] Error al cargar: {e}")
        page.close()
        return []

    # Extraemos el total de páginas real
    total_paginas = pagina_inicio
    try:
        texto_resumen = page.locator(".search-results-summary").inner_text(timeout=5000)
        match = re.search(r"de (\d+)\)", texto_resumen)
        if match:
            total_paginas = int(match.group(1))
    except Exception:
        pass

    # Verificamos si la web aceptó el parámetro URL o si nos dejó en la página 1
    pagina_actual_dom = 1
    try:
        texto_resumen = page.locator(".search-results-summary").inner_text(timeout=2000)
        match_actual = re.search(r"página (\d+) de", texto_resumen)
        if match_actual:
            pagina_actual_dom = int(match_actual.group(1))
    except:
        pass

    # ==========================================
    # LÓGICA DE FAST-FORWARD
    # ==========================================
    if pagina_actual_dom < pagina_inicio:
        print(f"[*] El salto por URL fue bloqueado. Avanzando rápido hasta la pág {pagina_inicio}...")
        for p in range(pagina_actual_dom, pagina_inicio):
            try:
                boton_siguiente = page.locator("#pagination-controls button:last-child")
                boton_siguiente.wait_for(state="attached", timeout=5000)
                boton_siguiente.evaluate("el => el.click()")
                
                texto_esperado = f"página {p + 1} de"
                page.wait_for_function(
                    f"() => document.querySelector('.search-results-summary') && document.querySelector('.search-results-summary').innerText.includes('{texto_esperado}')", 
                    timeout=15000 
                )
                time.sleep(0.3) # Pausa hiper-corta solo para no saturar Chromium
            except Exception as e:
                print(f"[!] Error avanzando rápido en la pág {p}: {e}")
                break
        
        print("[+] Llegamos a la página objetivo. Retomando extracción de datos...")
        time.sleep(3) # Damos tiempo a que carguen bien los precios de la página objetivo

    # ==========================================
    # BUCLE NORMAL DE EXTRACCIÓN
    # ==========================================
    selector_tarjeta = ".product:not(.is-skeleton)"
    
    for pagina_actual in range(pagina_inicio, total_paginas + 1):
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
        
        # Navegación con reintentos
        if pagina_actual < total_paginas:
            boton_siguiente = page.locator("#pagination-controls button:last-child")
            texto_esperado = f"página {pagina_actual + 1} de"
            
            max_intentos = 3
            intento_actual = 0
            exito_paginacion = False
            
            while intento_actual < max_intentos and not exito_paginacion:
                try:
                    boton_siguiente.wait_for(state="attached", timeout=10000)
                    boton_siguiente.evaluate("el => el.click()")
                    
                    page.wait_for_function(
                        f"() => document.querySelector('.search-results-summary') && document.querySelector('.search-results-summary').innerText.includes('{texto_esperado}')", 
                        timeout=20000 
                    )
                    exito_paginacion = True
                    time.sleep(random.uniform(2.5, 4.5))
                except Exception:
                    intento_actual += 1
                    tiempo_espera = 15 * intento_actual
                    print(f"    [!] Atasco en página {pagina_actual + 1} (Intento {intento_actual}/{max_intentos}). Servidor ocupado.")
                    if intento_actual < max_intentos:
                        print(f"    [*] Aplicando backoff... esperando {tiempo_espera}s.")
                        time.sleep(tiempo_espera)
                    else:
                        print(f"[!] Agotados los intentos. Guardando progreso...")
            
            if not exito_paginacion:
                break

    page.close()
    return datos_tienda

def main():
    catalogo_total = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False, 
            args=["--disable-blink-features=AutomationControlled"]
        ) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768}
        )
        
        for tienda, pag_inicio in TIENDAS_RESCATE.items(): 
            resultados = extraer_tienda_rescate(context, tienda, pag_inicio)
            catalogo_total.extend(resultados)
            
            time.sleep(random.uniform(5, 8)) 
            
        browser.close()
        
    if catalogo_total:
        df = pd.DataFrame(catalogo_total)
        df.drop_duplicates(subset=["ID_Dataprecio", "Tienda"], inplace=True)
        
        fecha_str = time.strftime("%Y%m%d_%H%M")
        archivo_salida = f"catalogo_rescate_dataprecio_{fecha_str}.csv"
        df.to_csv(archivo_salida, index=False, encoding='utf-8')
        
        print(f"\n[+] ¡Rescate Completado! CSV guardado con {len(df)} registros en '{archivo_salida}'.")
    else:
        print("\n[-] La extracción de rescate falló o no obtuvo datos.")

if __name__ == "__main__":
    main()
