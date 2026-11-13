import pandas as pd
import numpy as np
import re
import unicodedata
import os
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter

def normalizar_nombre(texto):
    if pd.isna(texto):
        return ""
    texto = str(texto)
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8')
    texto = texto.replace(',', '').upper().strip()
    texto = re.sub(r'\s+', ' ', texto)
    return texto

def procesar_ean(ean):
    if pd.isna(ean):
        return "", False
    ean_str = re.sub(r'\D', '', str(ean).split('.')[0])
    if not ean_str:
        return "", False
    ean_13 = ean_str.zfill(13)
    if len(ean_13) > 13:
        return ean_13, False
    try:
        suma = sum(int(ean_13[i]) * (1 if i % 2 == 0 else 3) for i in range(12))
        check_digit_calculado = (10 - (suma % 10)) % 10
        check_digit_real = int(ean_13[12])
        return ean_13, (check_digit_calculado == check_digit_real)
    except:
        return ean_13, False

def extraer_unidades(nombre):
    if not nombre:
        return "OTRO"
    patron = r'\b(\d+(?:[.,]\d+)?)\s*(KG|G|GR|GRS|MG|L|LT|LTS|ML|CC|OZ|LB|LBS|UN|UND|UNID)\b'
    match = re.search(patron, nombre)
    if match:
        unidad = match.group(2)
        if unidad in ['G', 'GR', 'GRS']: unidad = 'GR'
        elif unidad in ['L', 'LT', 'LTS']: unidad = 'LT'
        elif unidad in ['UN', 'UND', 'UNID']: unidad = 'UND'
        return unidad
    return "OTRO"

def buscar_columna(columnas, alias_list):
    for col in columnas:
        col_norm = str(col).lower().replace('_', ' ').replace('-', ' ')
        for alias in alias_list:
            if alias in col_norm:
                return col
    return None

# --- NUEVA FUNCIÓN PARA LIMPIAR PRECIOS CON TEXTO Y COMAS ---
def limpiar_precio(val):
    if pd.isna(val) or str(val).strip() == "":
        return np.nan
    
    # Convierte a texto, quita palabras comunes y espacios
    val_str = str(val).upper()
    val_str = val_str.replace('REF.', '').replace('REF', '').replace('$', '').strip()
    
    # Si viene en formato venezolano (ej: 1.500,99), quitamos el punto de miles y cambiamos la coma a punto
    # Para ser seguros, si solo tiene una coma (ej: 1,99), la pasamos a punto.
    # Si tiene ambos, removemos el punto y pasamos coma a punto.
    if ',' in val_str and '.' in val_str:
        val_str = val_str.replace('.', '') # Quita separador de miles
        
    val_str = val_str.replace(',', '.') # Transforma coma decimal en punto para Python
    
    # Finalmente, nos aseguramos de quitar cualquier otra letra rara que haya quedado
    val_str = re.sub(r'[^\d.]', '', val_str)
    
    try:
        return float(val_str)
    except:
        return np.nan
# -----------------------------------------------------------

def aplicar_formato_excel(writer, df, sheet_name='Catalogo'):
    workbook = writer.book
    worksheet = writer.sheets[sheet_name]
    
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    align_center = Alignment(horizontal="center", vertical="center")
    
    for col_num, value in enumerate(df.columns.values):
        cell = worksheet.cell(row=1, column=col_num + 1)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = align_center

    worksheet.auto_filter.ref = worksheet.dimensions
    worksheet.freeze_panes = 'A2'

    for i, col in enumerate(df.columns):
        datos_validos = df[col].dropna()
        longitud_max = len(str(col))
        if not datos_validos.empty:
            max_dato = datos_validos.map(lambda x: len(str(x))).max()
            longitud_max = max(longitud_max, max_dato)
            
        ancho_optimo = min(longitud_max + 3, 50) 
        col_letter = get_column_letter(i + 1)
        worksheet.column_dimensions[col_letter].width = ancho_optimo

def normalizar_dataset(ruta_entrada, ruta_salida):
    print(f"\n--- Procesando archivo: {ruta_entrada} ---")
    
    try:
        if ruta_entrada.endswith('.csv'):
            df = pd.read_csv(ruta_entrada)
        else:
            df = pd.read_excel(ruta_entrada)
    except Exception as e:
        print(f"❌ Error al leer el archivo: {e}")
        return

    columnas_orig = list(df.columns)

    col_ean      = buscar_columna(columnas_orig, ['ean', 'barcode', 'gtin', 'codigo', 'sku'])
    col_nombre   = buscar_columna(columnas_orig, ['nombre', 'name'])
    col_img      = buscar_columna(columnas_orig, ['imagen', 'image', 'img', 'url'])
    col_p_base   = buscar_columna(columnas_orig, ['precio base', 'price base', 'precio'])
    col_p_final  = buscar_columna(columnas_orig, ['precio final', 'price final', 'precio paquete'])
    
    col_marca    = buscar_columna(columnas_orig, ['marca', 'brand'])
    col_submarca = buscar_columna(columnas_orig, ['submarca', 'subbrand'])
    col_depto    = buscar_columna(columnas_orig, ['departamento', 'department', 'depto'])
    col_subdepto = buscar_columna(columnas_orig, ['subdepartamento'])
    col_cat      = buscar_columna(columnas_orig, ['categoria', 'category', 'cat'])
    col_subcat   = buscar_columna(columnas_orig, ['subcategoria'])

    df_plantilla = pd.DataFrame(columns=[
        'GTIN', 'GTIN_VALIDO', 'NOMBRE', 'UNIDAD', 'MARCA', 'SUBMARCA', 
        'DEPARTAMENTO', 'SUBDEPARTAMENTO', 'CATEGORIA', 
        'SUBCATEGORIA', 'PRECIO BASE', 'IVA', 'IMAGEN'
    ])

    if col_ean:
        resultados_ean = df[col_ean].apply(procesar_ean)
        df_plantilla['GTIN'] = resultados_ean.apply(lambda x: x[0] if x else "")
        df_plantilla['GTIN_VALIDO'] = resultados_ean.apply(lambda x: x[1] if x else False)
    else:
        df_plantilla['GTIN'] = ""
        df_plantilla['GTIN_VALIDO'] = False

    if col_nombre:
        df_plantilla['NOMBRE'] = df[col_nombre].apply(normalizar_nombre)
        df_plantilla['UNIDAD'] = df_plantilla['NOMBRE'].apply(extraer_unidades)
    else:
        df_plantilla['NOMBRE'] = ""
        df_plantilla['UNIDAD'] = "OTRO"

    df_plantilla['MARCA'] = df[col_marca] if col_marca else ""
    df_plantilla['SUBMARCA'] = df[col_submarca] if col_submarca else ""
    df_plantilla['DEPARTAMENTO'] = df[col_depto] if col_depto else ""
    df_plantilla['SUBDEPARTAMENTO'] = df[col_subdepto] if col_subdepto else ""
    df_plantilla['CATEGORIA'] = df[col_cat] if col_cat else ""
    df_plantilla['SUBCATEGORIA'] = df[col_subcat] if col_subcat else ""
    df_plantilla['IMAGEN'] = df[col_img] if col_img else ""

    # --- LÓGICA DE PRECIOS MEJORADA ---
    precio_base_final = ""
    iva_calculado = ""

    if col_p_base and col_p_final and col_p_base != col_p_final:
        # Aplicamos la nueva función de limpieza a ambas columnas
        p_base = df[col_p_base].apply(limpiar_precio)
        p_final = df[col_p_final].apply(limpiar_precio)
        
        ratio = p_final / p_base
        total_validos = ratio.notna().sum()
        
        if total_validos > 0:
            porcentaje_iguales = (ratio == 1).sum() / total_validos
            if porcentaje_iguales > 0.8:
                print(f"🚨 ALERTA: Cálculo de IVA defectuoso ({porcentaje_iguales*100:.0f}% coinciden). Eliminando precio final.")
                precio_base_final = p_base
                iva_calculado = 0
            else:
                print("✓ Validación de IVA aprobada. Calculando diferencial...")
                precio_base_final = p_base
                # Calculamos el IVA restando el final menos el base (manteniendo redondeo a 2 decimales para evitar números largos)
                iva_calculado = (p_final - p_base).round(2)
        else:
            precio_base_final = p_base
            iva_calculado = 0
            
    elif col_p_base:
        precio_base_final = df[col_p_base].apply(limpiar_precio)
        iva_calculado = 0
    elif col_p_final:
        precio_base_final = df[col_p_final].apply(limpiar_precio)
        iva_calculado = 0

    # Llenamos la plantilla
    df_plantilla['PRECIO BASE'] = precio_base_final
    df_plantilla['IVA'] = iva_calculado
    # ----------------------------------

    try:
        if ruta_salida.endswith('.csv'):
            df_plantilla.to_csv(ruta_salida, index=False, encoding='utf-8-sig')
            print(f"🚀 Terminado. CSV estandarizado en: {ruta_salida}")
        else:
            with pd.ExcelWriter(ruta_salida, engine='openpyxl') as writer:
                df_plantilla.to_excel(writer, index=False, sheet_name='Catalogo')
                aplicar_formato_excel(writer, df_plantilla, 'Catalogo')
            print(f"🚀 Terminado. Excel estandarizado y formateado en: {ruta_salida}")
    except Exception as e:
        print(f"❌ Error al guardar {ruta_salida}: {e}")

# --- EJECUCIÓN MASIVA ---
archivos = [
    "kuantip_productos_huerfanos_completo.csv",
    #"prods_kalea.xlsx",
    #"riomarket_maestro_total.xlsx",
    #"catalogo_emporium.xlsx",
    #"maestro_super_fresh_market.xlsx",
    #"Catalogo_Choppi_2Doce_Market.xlsx",
    #"Catalogo_Choppi_Automercado_Santa_Rosa.xlsx",
    #"Catalogo_Choppi_Automercado_Santa_Paula.xlsx",
    #"Catalogo_Choppi_Luvebras.xlsx",
    #"Catalogo_Choppi_Mercato.xlsx",
    #"Catalogo_Choppi_Plazas.xlsx"
]

for archivo in archivos:
    if os.path.exists(archivo):
        salida = "ESTANDARIZADO_" + archivo
        normalizar_dataset(archivo, salida)