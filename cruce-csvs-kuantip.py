import requests
import csv
import time
import os

# ================= CONFIGURACIÓN =================
ARCHIVO_CSV_ENTRADA = "C:\\Users\\USUARIO\\Documents\\1. Work\\Kuantip\\scripts\\skus-tuzonamarket\\productos_cigarros.csv"
ARCHIVO_CSV_SALIDA = "productos_cigarros_nuevos.csv"

# Reemplaza con tu token actual
TOKEN_BEARER = os.environ["KUANTIP_BACKOFFICE_TOKEN"] 
# =================================================

def verificar_y_filtrar_skus():
    if not os.path.exists(ARCHIVO_CSV_ENTRADA):
        print(f"❌ Error: No se encontró el archivo '{ARCHIVO_CSV_ENTRADA}'")
        return

    headers = {
        "Accept": "*/*",
        "Authorization": f"{TOKEN_BEARER}",
        "Origin": "https://backoffice-staging.kuantip.app",
        "Referer": "https://backoffice-staging.kuantip.app/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        "Ngrok-Skip-Browser-Warning": "1"
    }

    productos_nuevos = []
    total_procesados = 0
    total_existentes = 0

    print(f"Abriendo '{ARCHIVO_CSV_ENTRADA}' para validación...\n")

    with open(ARCHIVO_CSV_ENTRADA, mode='r', encoding='utf-8') as f_in:
        lector = csv.DictReader(f_in)
        campos = lector.fieldnames

        for fila in lector:
            total_procesados += 1
            sku_actual = fila.get('sku', '').strip()
            nombre_actual = fila.get('nombre', 'Sin Nombre')

            # 1. Si el producto no tiene SKU válido desde TuZonaMarket, lo conservamos directamente
            if not sku_actual or sku_actual.lower() == "sin sku":
                print(f"[{total_procesados}] ⚠️ Sin SKU válido: {nombre_actual[:30]}... -> GUARDANDO")
                productos_nuevos.append(fila)
                continue

            # 2. Consultar la API de Kuantip
            url_busqueda = f"https://api-staging.kuantip.app/products/sku/{sku_actual}"
            
            try:
                respuesta = requests.get(url_busqueda, headers=headers)
                
                if respuesta.status_code == 200:
                    datos_json = respuesta.json()
                    
                    # 3. La lógica clave: Si NO existe la llave 'item', el producto es nuevo
                    if "item" not in datos_json:
                        print(f"[{total_procesados}] ✅ NUEVO (SKU {sku_actual}): {nombre_actual[:30]}... -> GUARDANDO")
                        productos_nuevos.append(fila)
                    else:
                        print(f"[{total_procesados}] ❌ EXISTE (SKU {sku_actual}): {nombre_actual[:30]}... -> DESCARTANDO")
                        total_existentes += 1
                else:
                    print(f"[{total_procesados}] ⚠️ Error HTTP {respuesta.status_code} al buscar SKU {sku_actual}")
                    # Ante la duda por error de servidor, mejor guardarlo para revisión manual
                    productos_nuevos.append(fila)

            except Exception as e:
                print(f"[{total_procesados}] ⚠️ Excepción con SKU {sku_actual}: {e}")
                productos_nuevos.append(fila)

            # Pausa para no saturar la API (Rate Limiting)
            time.sleep(0.3)

    # 4. Guardar los resultados filtrados
    with open(ARCHIVO_CSV_SALIDA, mode='w', newline='', encoding='utf-8') as f_out:
        escritor = csv.DictWriter(f_out, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(productos_nuevos)

    print("\n" + "="*45)
    print("📊 RESULTADOS DE LA VALIDACIÓN POR SKU")
    print("="*45)
    print(f"Total procesados del CSV:    {total_procesados}")
    print(f"Ya existían en Kuantip:      {total_existentes}")
    print(f"Nuevos productos guardados:  {len(productos_nuevos)}")
    print(f"Archivo generado: '{ARCHIVO_CSV_SALIDA}'")

if __name__ == "__main__":
    verificar_y_filtrar_skus()