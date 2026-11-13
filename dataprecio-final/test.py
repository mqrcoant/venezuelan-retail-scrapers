from playwright.sync_api import sync_playwright
import time
import json

def cazar_datos_en_memoria(url_busqueda):
    print(f"[*] Iniciando navegador para interceptar: {url_busqueda}")
    
    with sync_playwright() as p:
        # Lo dejamos en headless=False para que veas que la página cargue correctamente
        browser = p.chromium.launch(headless=False) 
        page = browser.new_page()
        
        # 1. INYECCIÓN DEL ESPÍA
        # Este script se ejecuta antes que cualquier código propio de Dataprecio
        page.add_init_script("""
            const originalParse = JSON.parse;
            window.__BOTIN_INTERCEPTADO__ = [];
            
            JSON.parse = function(text, reviver) {
                const resultado = originalParse(text, reviver);
                
                try {
                    // Verificamos si el objeto parseado tiene estructura de catálogo
                    if (resultado && typeof resultado === 'object') {
                        
                        // Escenario A: Vienen dentro de una llave 'hits'
                        if (resultado.hits && Array.isArray(resultado.hits)) {
                            window.__BOTIN_INTERCEPTADO__.push(...resultado.hits);
                        } 
                        // Escenario B: Vienen dentro de una llave 'data' o 'productos'
                        else if (resultado.data && Array.isArray(resultado.data)) {
                            window.__BOTIN_INTERCEPTADO__.push(...resultado.data);
                        }
                        else if (resultado.productos && Array.isArray(resultado.productos)) {
                            window.__BOTIN_INTERCEPTADO__.push(...resultado.productos);
                        }
                        // Escenario C: Es un array directo donde el primer elemento tiene 'name' o 'nombre'
                        else if (Array.isArray(resultado) && resultado.length > 0 && (resultado[0].name || resultado[0].nombre)) {
                            window.__BOTIN_INTERCEPTADO__.push(...resultado);
                        }
                    }
                } catch (e) {
                    // Ignoramos silenciosamente para no interrumpir el flujo de la web
                }
                
                return resultado;
            };
        """)
        
        print("[*] Espía inyectado en JSON.parse(). Navegando a la web...")
        page.goto(url_busqueda)
        
        # 2. ESPERA DE RENDERIZADO
        try:
            page.wait_for_selector(".product", timeout=15000)
            print("[+] Productos detectados en pantalla. Dando tiempo al espía para recolectar...")
            time.sleep(4) # Pausa de seguridad para que termine de parsear todo
        except Exception as e:
            print(f"[!] Aviso: No se detectó el selector de productos. Error: {e}")
        
        # 3. EXTRACCIÓN DEL BOTÍN
        datos_crudos = page.evaluate("window.__BOTIN_INTERCEPTADO__")
        
        browser.close()
        return datos_crudos

if __name__ == "__main__":
    # URL de prueba apuntando a un filtro específico
    url_prueba = "https://www.dataprecio.com/?store=Farmatodo"
    
    resultados = cazar_datos_en_memoria(url_prueba)
    
    if resultados and len(resultados) > 0:
        print(f"\n[+] ¡Éxito! Se interceptaron {len(resultados)} fragmentos de productos.")
        
        # Guardamos todo en un archivo JSON estructurado
        nombre_archivo = "volcado_memoria_dataprecio.json"
        with open(nombre_archivo, "w", encoding="utf-8") as f:
            json.dump(resultados, f, indent=4, ensure_ascii=False)
            
        print(f"[+] Archivo '{nombre_archivo}' generado correctamente.")
        
        # Imprimimos solo las llaves (keys) del primer producto para ver qué campos viajan realmente
        print("\n--- Estructura del primer producto interceptado ---")
        if isinstance(resultados[0], dict):
            for llave in resultados[0].keys():
                print(f" - {llave}")
        else:
            print(resultados[0])
            
    else:
        print("\n[-] El espía no capturó nada útil. Es posible que la web desencripte de otra forma o la estructura del JSON sea diferente.")