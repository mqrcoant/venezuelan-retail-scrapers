import os
import requests
import pandas as pd
import time
import random

def scrape_kuantip_orphans_stealth():
    url = "https://api-staging.kuantip.app/products-orphans"
    
    # Cabeceras copiadas de tu script para emular la conexión del Backoffice
    headers = {
        "Accept": "*/*",
        "Authorization": f"Bearer {os.environ['KUANTIP_BACKOFFICE_TOKEN']}", 
        "Origin": "https://backoffice-staging.kuantip.app",
        "Referer": "https://backoffice-staging.kuantip.app/",
        "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36",
        "Ngrok-Skip-Browser-Warning": "1"
    }
    
    params = {
        "size": 1000,
        "order_by": "created_at",
        "order_dir": "desc",
        "sku": "false",
        "page": 0
    }
    
    print("Iniciando conexión con la API de Kuantip (Huérfanos)...")
    
    try:
        # Primera llamada para obtener los metadatos de paginación (total de páginas)
        response = requests.get(url, headers=headers, params=params, timeout=20)
        
        if response.status_code != 200:
            print(f"Error de autenticación o conexión: {response.status_code}")
            return
            
        data = response.json()
        
        # Tomamos el total de páginas y total de items si la API los devuelve, sino usamos 11 por defecto
        total_pages = data.get("total_pages", 11) 
        total_items = data.get("total", "aprox 10k")
        
        print(f"Total de productos a extraer: {total_items} repartidos en {total_pages} páginas.")
        
        all_items = []
        
        # Iteramos sobre el rango de páginas exactamente como en tu script de referencia
        for page in range(total_pages):
            print(f"-> Procesando página {page}...")
            params["page"] = page
            
            # Para la página 0 ya tenemos la respuesta (podríamos optimizar, pero mantenemos tu estructura por simplicidad)
            if page != 0:
                resp = requests.get(url, headers=headers, params=params, timeout=20)
                if resp.status_code != 200:
                    print(f"Error en página {page}: Status {resp.status_code}. Saltando...")
                    continue
                data = resp.json()
                
            items = data.get("items", [])
            
            if not items:
                print(f"   La página {page} vino vacía. Finalizando paginación temprana.")
                break
                
            all_items.extend(items)
            
            # --- ESPERA ALEATORIA PARA PASAR DESAPERCIBIDO ---
            tiempo_espera = random.uniform(2.5, 5.8)
            print(f"   Esperando {tiempo_espera:.2f} segundos para simular comportamiento humano...")
            time.sleep(tiempo_espera)
            
        if all_items:
            # Convertimos toda la lista a DataFrame manteniendo el esquema exacto del JSON
            df = pd.json_normalize(all_items)
            csv_filename = "kuantip_productos_huerfanos_completo.csv"
            
            # Guardamos el CSV
            df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
            
            print("\n¡Extracción completada con éxito!")
            print(f"Total real de productos huérfanos extraídos: {len(all_items)}")
            print(f"El archivo se guardó como: {csv_filename}")
        else:
            print("No se encontraron productos para guardar.")

    except Exception as e:
        print(f"Error al conectar con la API: {e}")

if __name__ == "__main__":
    scrape_kuantip_orphans_stealth()