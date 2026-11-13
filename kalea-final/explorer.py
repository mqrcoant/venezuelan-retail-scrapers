import requests
import json

API_BASE = "https://mywkxuvnbnzfxdbswojh.supabase.co/rest/v1"
API_KEY = "sb_publishable_kBqxEZ84Hm_AIwHrj0YEIg_LUG4c21B"

HEADERS = {
    "apikey": API_KEY,
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json"
}

def explorar_supabase():
    # 1. Intentar obtener el esquema OpenAPI completo (lista de tablas y vistas)
    print("[*] Consultando ruta raíz para extraer esquema OpenAPI...")
    res_schema = requests.get(f"{API_BASE}/", headers=HEADERS)
    
    if res_schema.status_code == 200:
        try:
            schema = res_schema.json()
            # En OpenAPI 2.0 (PostgREST), las tablas están en 'definitions' o 'paths'
            tablas = list(schema.get("definitions", {}).keys()) or list(schema.get("paths", {}).keys())
            print(f"[+] Tablas/Endpoints expuestos ({len(tablas)}): {tablas}")
            
            # Si 'definitions' existe, podemos ver las columnas exactas de cada tabla de interés
            for t in tablas:
                if any(k in t.lower() for k in ["inv", "stock", "prod", "store", "ware"]):
                    cols = list(schema.get("definitions", {}).get(t, {}).get("properties", {}).keys())
                    print(f"    -> Columnas en '{t}': {cols}")
        except Exception as e:
            print(f"[!] La raíz respondió 200 pero no es un JSON OpenAPI estándar: {e}")
    else:
        print(f"[!] Esquema raíz bloqueado o no disponible (HTTP {res_schema.status_code}).")

    # 2. Consultar 1 registro completo de 'inventory' directamente
    print("\n[*] Inspeccionando todas las columnas de la tabla 'inventory'...")
    res_inv = requests.get(f"{API_BASE}/inventory", headers=HEADERS, params={"select": "*", "limit": 1})
    if res_inv.status_code == 200 and res_inv.json():
        registro = res_inv.json()[0]
        print("[+] Columnas detectadas en 'inventory':")
        print(json.dumps(registro, indent=4, ensure_ascii=False))
    else:
        print(f"[!] Error al leer 'inventory' directamente: HTTP {res_inv.status_code} - {res_inv.text}")

    # 3. Consultar 1 registro completo de 'products' con relaciones abiertas
    print("\n[*] Inspeccionando un producto con 'inventory(*)' y 'offers(*)'...")
    params_prod = {
        "select": "*,inventory(*),offers(*)",
        "limit": 1
    }
    res_prod = requests.get(f"{API_BASE}/products", headers=HEADERS, params=params_prod)
    if res_prod.status_code == 200 and res_prod.json():
        print("[+] Estructura completa de un producto:")
        print(json.dumps(res_prod.json()[0], indent=4, ensure_ascii=False))

if __name__ == "__main__":
    explorar_supabase()