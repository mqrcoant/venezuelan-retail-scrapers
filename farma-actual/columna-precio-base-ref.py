import pandas as pd
import re
import os
from pathlib import Path

# Configuración de archivos
ARCHIVO_ENTRADA = Path(__file__).resolve().parent / 'maestro_tu_farmacia_actual.csv'
ARCHIVO_SALIDA = Path(__file__).resolve().parent / 'maestro_tu_farmacia_actual_base.csv'

# Tasa del BCV del día en que se hizo el scraping
TASA_BCV = float(os.environ['BCV_RATE'])

# Nombre de la columna que contiene el precio en el CSV
COLUMNA_PRECIO = 'precio_bs'  # <--- Ajustar si se llama diferente (ej: 'precio_bs')

def limpiar_precio(precio_str):
    """Limpia el formato '1.131,08 Bs' y lo convierte a float"""
    if pd.isna(precio_str):
        return float('nan')
    p = str(precio_str)
    # Quitar cualquier texto como 'Bs', letras o espacios
    p = re.sub(r'[^\d,\.]', '', p)
    
    # Transformar formato de miles/decimales: 1.131,08 -> 1131.08
    if '.' in p and ',' in p:
        p = p.replace('.', '').replace(',', '.')
    elif ',' in p:
        p = p.replace(',', '.')
        
    try:
        return float(p)
    except ValueError:
        return float('nan')

def main():
    print(f"Procesando {ARCHIVO_ENTRADA}...")
    try:
        df = pd.read_csv(ARCHIVO_ENTRADA, dtype={'sku_interno': str})
        
        if COLUMNA_PRECIO not in df.columns:
            print(f"Error: La columna '{COLUMNA_PRECIO}' no existe. Columnas disponibles: {list(df.columns)}")
            return

        # 1. Convertir texto a número
        df['precio_con_iva_bs'] = df[COLUMNA_PRECIO].apply(limpiar_precio)
        df = df.loc[df['precio_con_iva_bs'] > 0].copy()

        # La tienda no publica el IVA individual en el listado ni en el detalle.
        # Solo calcular base si un futuro scraper aporta una tasa explícita.
        tasas = pd.to_numeric(df['iva_pct'], errors='coerce') if 'iva_pct' in df else pd.Series(float('nan'), index=df.index)
        conocidas = tasas.isin([0, 16])
        df['estado_iva'] = conocidas.map({True: 'informado', False: 'no_informado'})
        df['tasa_bcv'] = TASA_BCV
        df['precio_base_bs'] = (df['precio_con_iva_bs'] / (1 + tasas / 100)).where(conocidas)
        df['precio_base_ref'] = (df['precio_base_bs'] / TASA_BCV).round(2)

        # Exportar el nuevo CSV
        df.to_csv(ARCHIVO_SALIDA, index=False)
        print(f"¡Listo! Archivo generado: {ARCHIVO_SALIDA}")

    except FileNotFoundError:
        print(f"Error: No se encontró {ARCHIVO_ENTRADA} en este directorio.")
    except Exception as e:
        print(f"Ocurrió un error inesperado: {e}")

if __name__ == "__main__":
    main()
