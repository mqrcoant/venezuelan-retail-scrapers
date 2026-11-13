import pandas as pd
import os

# 1. Cargar el archivo original
archivo_origen = 'prods_dataprecio.csv'
df = pd.read_csv(archivo_origen)

# 2. Crear la carpeta "comercios-separados"
carpeta_salida = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'finales', 'dataprecio')
if not os.path.exists(carpeta_salida):
    os.makedirs(carpeta_salida)

# 3. Obtener la lista de tiendas únicas
tiendas_unicas = df['Tienda'].dropna().unique()
print(f"Se encontraron {len(tiendas_unicas)} tiendas. Generando archivos Excel...")

# 4. Iterar sobre cada tienda
for tienda in tiendas_unicas:
    # Crear una copia de los datos de la tienda
    df_tienda = df[df['Tienda'] == tienda].copy()
    
    # Asegurarnos de que el precio se lea como número y ordenar de A a Z internamente
    if 'Precio_USD' in df_tienda.columns:
        df_tienda['Precio_USD'] = pd.to_numeric(df_tienda['Precio_USD'], errors='coerce')
        df_tienda = df_tienda.sort_values(by='Precio_USD', ascending=True)
    
    # Nombre del archivo 
    nombre_archivo = str(tienda).replace(' ', '_').replace('/', '-').lower() + '.xlsx'
    ruta_salida = os.path.join(carpeta_salida, nombre_archivo)
    
    # Guardar en formato Excel aplicando autofiltros nativos
    with pd.ExcelWriter(ruta_salida, engine='xlsxwriter') as writer:
        df_tienda.to_excel(writer, index=False, sheet_name='Productos')
        
        worksheet = writer.sheets['Productos']
        
        max_row = len(df_tienda)
        max_col = len(df_tienda.columns) - 1
        
        worksheet.autofilter(0, 0, max_row, max_col)
        
        # Ajustar visualmente el ancho de las columnas (CORREGIDO)
        for idx, col in enumerate(df_tienda.columns):
            # Usar .str.len() de pandas que maneja valores nulos de forma segura
            col_max_len = df_tienda[col].astype(str).str.len().max()
            
            # Si toda la columna fuera nula, prevé que col_max_len no sea NaN
            col_max_len = int(col_max_len) if pd.notna(col_max_len) else 0
            
            # Compara contra el largo del nombre de la columna
            max_len = max(col_max_len, len(str(col))) + 2
            
            # Ajustar la columna, con un límite máximo de 50
            worksheet.set_column(idx, idx, min(max_len, 50))
            
    print(f" - Creado: {ruta_salida} (con {len(df_tienda)} productos)")

print("¡Proceso completado exitosamente!")
