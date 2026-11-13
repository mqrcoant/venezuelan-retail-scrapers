import pandas as pd
import requests
import json
import unicodedata
import os
import time
from rapidfuzz import process, fuzz

# ================= CONFIGURACIÓN =================
LLM_API_URL = "https://openrouter.ai/api/v1/chat/completions" 
LLM_API_KEY = os.environ["OPENROUTER_API_KEY"] 
MODELO_LLM = "meta-llama/llama-3.3-70b-instruct" 

# Archivos de entrada y salida
CSVS_FUENTE = [
    "C:\\Users\\USUARIO\\Documents\\1. Work\\Kuantip\\scripts\\saas ✅ (solo faltantes)\\prods_saas.csv",
    "C:\\Users\\USUARIO\\Documents\\1. Work\\Kuantip\\scripts\\locatel ✅\\prods_locatel.csv",
    "C:\\Users\\USUARIO\\Documents\\1. Work\\Kuantip\\scripts\\farmago ✅ (solo faltantes E  iva original)\\maestro_farmago.csv",
    "C:\\Users\\USUARIO\\Documents\\1. Work\\Kuantip\\scripts\\gopharma ✅\\prods_gopharma.csv"
]

CSVS_DESTINO = [
    "C:\\Users\\USUARIO\\Documents\\1. Work\\Kuantip\\scripts\\badan\\maestro_badan_optimizado.csv",
    "C:\\Users\\USUARIO\\Documents\\1. Work\\Kuantip\\scripts\\farma-actual\\maestro_tu_farmacia_actual_base.csv",
]

# Nombres exactos de las columnas en tus archivos CSV
COL_NOMBRE = "nombre"
COL_EAN = "ean"
COL_PRECIO = "precio_base_ref"
# =================================================
def obtener_tasa_bcv():
    """Pide la tasa oficial del BCV por consola al usuario."""
    while True:
        try:
            tasa_str = input("Por favor, ingresa la tasa BCV del día para calcular los precios de Locatel (ej. 36.60): ")
            
            # Reemplazamos coma por punto por si usas teclado en español
            tasa_float = float(tasa_str.replace(",", "."))
            
            if tasa_float <= 0:
                print("  [!] La tasa debe ser mayor a cero.")
                continue
                
            print(f"  [OK] Tasa fijada en: {tasa_float} Bs/USD\n")
            return tasa_float
            
        except ValueError:
            print("  [!] Valor inválido. Por favor, ingresa un número válido (ej. 36.60).")
    
def normalizar_texto(texto):
    """Limpia el texto a minúsculas, quita tildes y espacios dobles."""
    if pd.isna(texto):
        return ""
    texto = str(texto).lower().strip()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    return " ".join(texto.split())

def normalizar_precio(precio_raw):
    """Convierte el precio a float. Si es 0.0 o inválido, devuelve None."""
    if pd.isna(precio_raw):
        return None
    try:
        precio_str = str(precio_raw).replace("$", "").replace("Bs", "").strip()
        
        # Si viene vacío después de limpiar
        if not precio_str:
            return None
            
        # Manejar formato europeo vs americano
        if "," in precio_str and "." in precio_str:
            precio_str = precio_str.replace(",", "") if precio_str.rfind(",") < precio_str.rfind(".") else precio_str.replace(".", "").replace(",", ".")
        else:
            precio_str = precio_str.replace(",", ".")
            
        precio_float = float(precio_str)
        
        # Ignorar precios que vienen en 0.0 por falta de stock
        if precio_float <= 0:
            return None
            
        return precio_float
    except (ValueError, TypeError):
        return None

def extraer_precio_gopharma(disponibilidad_str):
    """Extrae el precio de la primera tienda en el JSON de disponibilidad."""
    if pd.isna(disponibilidad_str):
        return None
    try:
        # Reemplazar comillas simples por dobles en caso de que pandas lo lea como string nativo de Python
        clean_str = str(disponibilidad_str).replace("'", '"')
        data = json.loads(clean_str)
        
        if isinstance(data, list) and len(data) > 0:
            # Tomamos el precio del primer diccionario en la lista
            precio = data[0].get("price")
            return float(precio) if precio is not None else None
    except Exception:
        return None
    return None

def construir_catalogo_maestro(rutas_fuente):
    """Carga todos los CSV fuente en un diccionario en memoria y normaliza precios."""
    print("Construyendo catálogo maestro desde las fuentes...")
    maestro = {}
    
    # 1. Obtener la tasa al inicio para no saturar la API
    tasa_bcv = obtener_tasa_bcv()
    
    for ruta in rutas_fuente:
        if not os.path.exists(ruta):
            print(f"  [!] Archivo fuente no encontrado: {ruta}")
            continue
            
        df = pd.read_csv(ruta)
        df_validos = df[df[COL_EAN].notna() & (df[COL_EAN].astype(str).str.strip() != '')]
        
        for _, row in df_validos.iterrows():
            nombre_orig = str(row[COL_NOMBRE])
            ean = str(row[COL_EAN]).strip()
            
            # 2. Lógica de precio según el proveedor
            if "gopharma" in ruta.lower():
                precio_bruto = extraer_precio_gopharma(row.get("disponibilidad"))
                precio = normalizar_precio(precio_bruto) if precio_bruto else None
                
            elif "locatel" in ruta.lower():
                # Locatel viene en Bolívares -> Convertimos a USD (Ref)
                precio_bs = normalizar_precio(row.get(COL_PRECIO)) 
                if precio_bs is not None and tasa_bcv > 0:
                    precio = round(precio_bs / tasa_bcv, 2)
                else:
                    precio = None
                    
            else:
                # Los demás ya vienen en formato Ref
                precio = normalizar_precio(row.get(COL_PRECIO))
            
            nombre_norm = normalizar_texto(nombre_orig)
            
            if nombre_norm not in maestro:
                maestro[nombre_norm] = {
                    "nombre_original": nombre_orig, 
                    "ean": ean,
                    "precio": precio
                }
                
    print(f"Catálogo maestro construido con {len(maestro)} productos únicos con EAN.\n")
    return maestro

def obtener_candidatos(nombre_objetivo, precio_objetivo, dict_maestro, limite=5):
    """Busca candidatos y aplica filtro de precio solo si ambos tienen precio válido."""
    nombre_norm = normalizar_texto(nombre_objetivo)
    opciones = list(dict_maestro.keys())
    
    resultados = process.extract(nombre_norm, opciones, scorer=fuzz.token_set_ratio, limit=limite * 2)
    
    candidatos = []
    for match in resultados:
        clave_norm = match[0]
        score = match[1]
        candidato_info = dict_maestro[clave_norm]
        precio_candidato = candidato_info["precio"]

        if score > 45: 
            # Validar solo si AMBOS productos tienen precio registrado
            if precio_objetivo is not None and precio_candidato is not None:
                # Doble validación para evitar división por cero
                if precio_objetivo > 0 and precio_candidato > 0:
                    ratio = precio_candidato / precio_objetivo
                    if ratio < 0.5 or ratio > 2.0:
                        continue # Descartar candidato por discrepancia grave

            # Si alguno no tiene precio (ej. SAAS en 0.0), se agrega igual para que el LLM decida
            candidatos.append({
                "nombre": candidato_info["nombre_original"],
                "ean": candidato_info["ean"],
                "precio": precio_candidato
            })
            
            if len(candidatos) == limite:
                break
                
    return candidatos

def validar_con_llm(producto_sin_ean, precio_objetivo, candidatos, max_reintentos=3):
    """Envía los candidatos al LLM para validación semántica con manejo de errores y reintentos."""
    if not candidatos:
        return None

    precio_str = f"${precio_objetivo}" if precio_objetivo else "Desconocido"

    prompt = f"""
    Eres un experto farmacéutico encargado de la deduplicación de catálogos. 
    Tu tarea es determinar si el 'Producto Objetivo' es EXACTAMENTE el mismo (misma marca, principio activo, concentración y presentación) que alguno de los 'Candidatos'.
    
    Producto Objetivo: "{producto_sin_ean}" | Precio: {precio_str}
    
    Candidatos:
    {json.dumps(candidatos, indent=2, ensure_ascii=False)}
    
    Criterios: 
    - El precio es una pista de empaque: diferencias moderadas son normales, pero diferencias abismales indican cambio de presentación.
    - Ignora el orden de las palabras (ej. "APIRET TAB 500 MG" es lo mismo que "ACETAMINOFEN 500 MG TAB APIRET").
    
    Responde ÚNICAMENTE en JSON válido con este formato exacto:
    {{"match_encontrado": true, "ean": "el_ean_del_candidato_seleccionado"}}
    O si no hay ninguno idéntico:
    {{"match_encontrado": false, "ean": null}}
    """

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODELO_LLM,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.0
    }

    for intento in range(max_reintentos):
        try:
            response_raw = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=15)
            response = response_raw.json()
            
            # Si la API responde con un error (ej. Rate Limit Exceeded)
            if 'error' in response:
                msj_error = response['error'].get('message', 'Error desconocido')
                print(f"  [!] Alerta API (Intento {intento+1}/{max_reintentos}): {msj_error}")
                
                if intento < max_reintentos - 1:
                    tiempo_espera = 3 ** (intento + 1) # Espera 3s, luego 9s, luego desiste
                    print(f"      Pausando {tiempo_espera} segundos...")
                    time.sleep(tiempo_espera)
                    continue
                else:
                    return None # Se agotaron los reintentos

            # Si la respuesta es exitosa, procesamos los choices
            respuesta_json = json.loads(response['choices'][0]['message']['content'])
            
            if respuesta_json.get("match_encontrado"):
                return respuesta_json.get("ean")
            return None # El LLM decidió que no hay match
            
        except KeyError:
            # Si el JSON no tiene 'choices' ni 'error'
            print(f"  [Error] Estructura inesperada de la API. Respuesta: {response_raw.text}")
            break
        except Exception as e:
            print(f"  [Error de red/conexión]: {e}")
            time.sleep(2) # Pausa breve antes del próximo intento si fue un fallo de red

    return None

def procesar_destinos(rutas_destino, dict_maestro):
    """Itera sobre los CSV destino y les asigna los EANs encontrados."""
    for ruta in rutas_destino:
        if not os.path.exists(ruta):
            print(f"Archivo destino no encontrado: {ruta}")
            continue
            
        print(f"--- Procesando {ruta} ---")
        df = pd.read_csv(ruta)
        
        # Asegurar que las columnas existan
        if COL_EAN not in df.columns:
            df[COL_EAN] = None

        asignados = 0
        total_a_procesar = len(df[pd.isna(df[COL_EAN]) | (df[COL_EAN].astype(str).str.strip() == "")])
        procesados = 0

        for index, row in df.iterrows():
            # Solo procesamos si NO tiene EAN
            if pd.isna(row[COL_EAN]) or str(row[COL_EAN]).strip() == "":
                nombre_obj = str(row[COL_NOMBRE])
                precio_obj = normalizar_precio(row.get(COL_PRECIO))
                
                # Fase 1: Algoritmo (Rápido)
                candidatos = obtener_candidatos(nombre_obj, precio_obj, dict_maestro)
                
                # Fase 2: LLM (Contexto)
                ean_match = validar_con_llm(nombre_obj, precio_obj, candidatos)
                procesados += 1
                
                if ean_match:
                    df.at[index, COL_EAN] = ean_match
                    asignados += 1
                    print(f"[{procesados}/{total_a_procesar}] [+] {nombre_obj} -> MATCH EAN: {ean_match}")
                else:
                    print(f"[{procesados}/{total_a_procesar}] [-] {nombre_obj} -> Sin match exacto")
                
                # Protección contra el Rate Limit (1.5 seg por petición es seguro para tiers gratuitos)
                time.sleep(1.5) 
        
        # Guardar archivo enriquecido
        nombre_salida = ruta.replace(".csv", "_con_ean.csv")
        df.to_csv(nombre_salida, index=False)
        print(f"Completado {ruta}: {asignados} EANs asignados. Guardado como '{nombre_salida}'\n")

if __name__ == "__main__":
    # 1. Cargar datos en memoria
    catalogo_maestro = construir_catalogo_maestro(CSVS_FUENTE)
    
    # 2. Iniciar el pipeline de enriquecimiento
    if catalogo_maestro:
        procesar_destinos(CSVS_DESTINO, catalogo_maestro)
    else:
        print("No se encontraron productos fuente válidos para cruzar.")