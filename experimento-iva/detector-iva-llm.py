import csv
import json
import requests
import time
import os

# Configura tu API Key aquí (OpenRouter, Groq, etc.)
API_KEY = os.environ["OPENROUTER_API_KEY"]
# Endpoint estándar compatible con OpenAI. Ejemplo para OpenRouter:
API_URL = "https://openrouter.ai/api/v1/chat/completions" 
MODELO = "meta-llama/llama-3.1-8b-instruct" # Puedes cambiarlo por el que prefieras

def es_taxable_segun_llm(nombre_producto, categoria):
    """
    Consulta al LLM si el producto es gravable (16% IVA) según las leyes venezolanas.
    """
    prompt_sistema = """Eres un experto fiscal del SENIAT en Venezuela. 
Tu única tarea es determinar si un producto está EXENTO de IVA o PAGA IVA (16%) basándote en su nombre y categoría.
Reglas de exención (Art. 18 Ley del IVA de Venezuela):
- EXENTOS: Medicamentos, principios activos, suplementos médicos, alimentos de la cesta básica (arroz, harina de maíz, huevos, leche no procesada, carnes naturales, pollo, vegetales, frutas, pan).
- PAGAN IVA (16%): Cuidado personal, belleza, hogar, chucherías, cereales procesados/azucarados (ej. Maizoritos), galletas, refrescos, bebidas alcohólicas, snacks.

Responde ÚNICAMENTE con la palabra "SI" (si paga 16% de IVA) o "NO" (si está exento). No des explicaciones, ni puntos, solo "SI" o "NO".
"""

    prompt_usuario = f"Categoría: {categoria}\nProducto: {nombre_producto}\n¿Paga 16% de IVA?"

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODELO,
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": prompt_usuario}
        ],
        "temperature": 0.0, # Temperatura 0 para respuestas deterministas
        "max_tokens": 5
    }

    try:
        respuesta = requests.post(API_URL, headers=headers, json=payload)
        respuesta_json = respuesta.json()
        
        texto_respuesta = respuesta_json['choices'][0]['message']['content'].strip().upper()
        
        # Limpiar la respuesta por si el LLM incluye algún carácter extra
        if "SI" in texto_respuesta or "SÍ" in texto_respuesta:
            return True
        else:
            return False
            
    except Exception as e:
        print(f"Error consultando LLM para '{nombre_producto}': {e}")
        # Por seguridad, si falla la API, asumimos que no es taxable o puedes cambiarlo a True
        return False

def procesar_csv_impuestos(archivo_entrada, archivo_salida):
    if not os.path.exists(archivo_entrada):
        print(f"Error: El archivo {archivo_entrada} no existe.")
        return

    productos_procesados = []

    with open(archivo_entrada, mode='r', encoding='utf-8') as file:
        lector = csv.DictReader(file)
        cabeceras = lector.fieldnames
        
        # Añadir las nuevas columnas si no existen
        if 'taxable_16' not in cabeceras:
            cabeceras.extend(['taxable_16', 'precio_final_bs'])

        filas = list(lector)
        total_filas = len(filas)
        
        print(f"Iniciando evaluación de {total_filas} productos...\n")

        for i, fila in enumerate(filas, 1):
            nombre = fila.get('nombre', 'Desconocido')
            categoria = fila.get('categoria', 'Sin Categoria')
            precio_base_str = fila.get('precio', '0')
            
            try:
                precio_base = float(precio_base_str)
            except ValueError:
                precio_base = 0.0

            # Consultar al LLM
            paga_iva = es_taxable_segun_llm(nombre, categoria)
            
            # Calcular el precio final
            if paga_iva:
                precio_final = round(precio_base * 1.16, 2)
                fila['taxable_16'] = 'SI'
            else:
                precio_final = precio_base
                fila['taxable_16'] = 'NO'
                
            fila['precio_final_bs'] = precio_final
            productos_procesados.append(fila)

            print(f"[{i}/{total_filas}] {nombre[:40]}... -> IVA: {fila['taxable_16']} | Final: {precio_final} Bs")
            
            # Pequeña pausa para evitar Rate Limits (Ajustar según los límites de tu API)
            time.sleep(0.5)

    # Guardar el nuevo CSV
    with open(archivo_salida, mode='w', newline='', encoding='utf-8') as file:
        escritor = csv.DictWriter(file, fieldnames=cabeceras)
        escritor.writeheader()
        escritor.writerows(productos_procesados)
        
    print(f"\n¡Proceso completado! Archivo guardado como: {archivo_salida}")

if __name__ == "__main__":
    # Puedes pasar cualquier archivo extraído previamente
    archivo_origen = input("Ingresa el nombre del archivo CSV a procesar (ej. maestro_farmago.csv): ")
    archivo_destino = archivo_origen.replace('.csv', '_con_precios_finales.csv')
    
    procesar_csv_impuestos(archivo_origen, archivo_destino)