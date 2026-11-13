import os
import requests
import csv
import time
import json
import random

def scrape_kuantip_merchants_csv():
    # Endpoint de comercios (merchants)
    url = "https://api-staging.kuantip.app/stores/merchants"
    
    headers = {
        "Accept": "*/*",
        "Authorization": os.environ["KUANTIP_BACKOFFICE_TOKEN"], 
        "Origin": "https://backoffice-staging.kuantip.app",
        "Referer": "https://backoffice-staging.kuantip.app/",
        "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36",
        "Ngrok-Skip-Browser-Warning": "1"
    }
    
    # Parámetros de la URL incluyendo status=active
    params = {
        "size": 100,
        "order_by": "created_at",
        "order_dir": "desc",
        "status": "active",
        "page": 0
    }
    
    nombre_archivo = 'kuantip_merchants.csv'
    
    print(f"Iniciando conexión con la API de Kuantip para extraer comercios a {nombre_archivo}...")
    
    with open(nombre_archivo, mode='w', newline='', encoding='utf-8') as archivo_csv:
        # Definimos las columnas incluyendo los datos aplanados de la cadena (branch)
        campos = [
            'id', 'name', 'identification', 'address', 'status', 
            'branch_id', 'branch_name', 'location', 'image', 'image_bg', 'raw_json'
        ]
        escritor_csv = csv.DictWriter(archivo_csv, fieldnames=campos)
        
        escritor_csv.writeheader()
        
        page = 0
        while True:
            print(f"-> Procesando página {page}...")
            params["page"] = page
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code != 200:
                print(f"Error de autenticación o conexión en página {page}: {response.status_code}")
                break
                
            data = response.json()
            
            # La respuesta tiene la lista bajo la clave "merchants"
            merchants = data.get("merchants", [])
            
            if not merchants:
                print("No se encontraron más resultados. Finalizando paginación.")
                break
                
            for item in merchants:
                # Eliminar las fechas para cumplir con el requerimiento
                item.pop("created_at", None)
                item.pop("updated_at", None)
                item.pop("deleted_at", None)
                
                # Extraer datos del objeto anidado 'branch'
                branch_data = item.get("branch", {})
                
                # Escribimos la fila en el CSV
                escritor_csv.writerow({
                    'id': item.get("id", ""),
                    'name': item.get("name", ""),
                    'identification': item.get("identification", ""),
                    'address': item.get("address", ""),
                    'status': item.get("status", ""),
                    'branch_id': branch_data.get("id", ""),
                    'branch_name': branch_data.get("name", ""),
                    'location': item.get("location", ""),
                    'image': item.get("image", ""),
                    'image_bg': item.get("image_bg", ""),
                    'raw_json': json.dumps(item)
                })
            
            # Pausa para simular comportamiento humano
            tiempo_espera = random.uniform(2.5, 5.8)
            print(f"   Esperando {tiempo_espera:.2f} segundos para simular lectura humana...")
            time.sleep(tiempo_espera)
            
            page += 1
            
    print(f"¡Extracción completada con éxito! El archivo '{nombre_archivo}' está listo y sin fechas.")

if __name__ == "__main__":
    scrape_kuantip_merchants_csv()