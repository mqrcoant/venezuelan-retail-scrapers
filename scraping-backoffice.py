import os
import requests
import sqlite3
import time
import json
import random # Agregado aquí arriba

def setup_db():
    conn = sqlite3.connect('kuantip_prods.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS productos_no_sku (
            id INTEGER PRIMARY KEY,
            name TEXT,
            brand_id INTEGER,
            brand_name TEXT,
            is_weight_based INTEGER DEFAULT 0,
            raw_json TEXT
        )
    ''')
    conn.commit()
    return conn

def scrape_kuantip_api():
    conn = setup_db()
    cursor = conn.cursor()
    
    url = "https://api-staging.kuantip.app/products"
    
    headers = {
        "Accept": "*/*",
        # TODO: Pega aquí tu Bearer token completo (eyJhbG...)
        "Authorization": os.environ["KUANTIP_BACKOFFICE_TOKEN"], 
        "Origin": "https://backoffice-staging.kuantip.app",
        "Referer": "https://backoffice-staging.kuantip.app/",
        "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36",
        "Ngrok-Skip-Browser-Warning": "1"
    }
    
    params = {
        "size": 1000,
        "order_by": "created_at_desc",
        "sku": "false"
        ##"certified": "false"
    }
    
    print("Iniciando conexión con la API de Kuantip...")
    
    params["page"] = 0
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code != 200:
        print(f"Error de autenticación o conexión: {response.status_code}")
        return
        
    data = response.json()
    total_pages = data.get("total_pages", 26)
    total_items = data.get("total", 0)
    
    print(f"Total de productos a extraer: {total_items} repartidos en {total_pages} páginas.")
    
    for page in range(total_pages):
        print(f"-> Procesando y guardando página {page}...")
        params["page"] = page
        
        if page != 0:
            resp = requests.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                print(f"Error en página {page}: Status {resp.status_code}. Saltando...")
                continue
            data = resp.json()
            
        items = data.get("items", [])
        
        for item in items:
            cursor.execute('''
                INSERT OR REPLACE INTO productos_no_sku (id, name, brand_id, brand_name, is_weight_based, raw_json)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                item.get("id"), 
                item.get("name"), 
                item.get("brand_id"), 
                item.get("brand_name"),
                int(item.get("is_weight_based", False)),
                json.dumps(item) 
            ))
            
        conn.commit()
        
        # --- AQUÍ ESTÁ EL CAMBIO PARA PASAR DESAPERCIBIDO ---
        tiempo_espera = random.uniform(2.5, 5.8)
        print(f"   Esperando {tiempo_espera:.2f} segundos para simular lectura humana...")
        time.sleep(tiempo_espera) 
        
    conn.close()
    print("¡Extracción completada con éxito! La base 'kuantip_prods.db' está lista.")

if __name__ == "__main__":
    scrape_kuantip_api()