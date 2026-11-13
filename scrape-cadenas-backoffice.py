import os
import requests
import csv
import time
import json
import random

def scrape_kuantip_branches_csv():
    # Endpoint obtenido de la imagen de red
    url = "https://api-staging.kuantip.app/stores/branches"
    
    headers = {
        "Accept": "*/*",
        # Token original de tu script
        "Authorization": os.environ["KUANTIP_BACKOFFICE_TOKEN"], 
        "Origin": "https://backoffice-staging.kuantip.app",
        "Referer": "https://backoffice-staging.kuantip.app/",
        "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36",
        "Ngrok-Skip-Browser-Warning": "1"
    }
    
    # Parámetros de la URL según la captura de red
    params = {
        "size": 100,
        "order_by": "created_at",
        "order_dir": "desc",
        "page": 0
    }
    
    nombre_archivo = 'kuantip_branches.csv'
    
    print(f"Iniciando conexión con la API de Kuantip para extraer sucursales a {nombre_archivo}...")
    
    # Abrimos el archivo CSV en modo escritura
    with open(nombre_archivo, mode='w', newline='', encoding='utf-8') as archivo_csv:
        # Definimos las columnas del CSV
        campos = ['id', 'name', 'image', 'image_bg', 'raw_json']
        escritor_csv = csv.DictWriter(archivo_csv, fieldnames=campos)
        
        # Escribimos la cabecera (primera fila)
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
            
            # La respuesta tiene la lista bajo la clave "branches"
            branches = data.get("branches", [])
            
            if not branches:
                print("No se encontraron más resultados. Finalizando paginación.")
                break
                
            for item in branches:
                # Eliminar las fechas para cumplir con el requerimiento "sin fechas"
                item.pop("created_at", None)
                item.pop("updated_at", None)
                item.pop("deleted_at", None)
                
                # Escribimos la fila en el CSV
                escritor_csv.writerow({
                    'id': item.get("id", ""),
                    'name': item.get("name", ""),
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
    scrape_kuantip_branches_csv()