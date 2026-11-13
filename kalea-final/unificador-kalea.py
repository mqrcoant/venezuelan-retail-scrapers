import csv
import re

def limpiar_ean(ean_raw):
    """Elimina absolutamente cualquier espacio en blanco dentro del string."""
    return re.sub(r'\s+', '', str(ean_raw))

def validar_ean(ean):
    """Verifica que el EAN contenga solo dígitos y tenga entre 4 y 13 caracteres."""
    return ean.isdigit() and 4 <= len(ean) <= 13

def unificar_y_filtrar_catalogos(archivo_val, archivo_ccs, archivo_validos, archivo_faltantes):
    print("[*] Iniciando deduplicación con base en Carabobo...")
    productos_unicos = {}
    
    def generar_llave(row, ean_limpio):
        nombre = str(row.get('name', '')).strip().lower()
        return (ean_limpio, nombre)

    # 1. Procesar Carabobo (Base Principal)
    try:
        with open(archivo_val, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                ean_limpio = limpiar_ean(row.get('ean', ''))
                llave = generar_llave(row, ean_limpio)
                
                productos_unicos[llave] = {
                    'ean': ean_limpio,  # Guardamos la versión ya sin espacios
                    'name': row.get('name', '').strip(),
                    'brand': row.get('brand', '').strip(),
                    'department': row.get('department', '').strip(),
                    'category': row.get('category', '').strip(),
                    'image_url': row.get('image_url', 'N/A').strip(), # <-- Imagen añadida
                    'disponibilidad': 'carabobo',
                    'price_base_bs_val': row.get('price_base_bs', ''),
                    'price_final_bs_val': row.get('price_final_bs', ''),
                    'price_base_ref_val': row.get('price_base_ref', ''),
                    'price_final_ref_val': row.get('price_final_ref', ''),
                    'price_base_bs_ccs': '',
                    'price_final_bs_ccs': '',
                    'price_base_ref_ccs': '',
                    'price_final_ref_ccs': ''
                }
        print(f"  -> {archivo_val} procesado (Base establecida).")
    except FileNotFoundError:
        print(f"[!] No se encontró el archivo: {archivo_val}")

    # 2. Procesar Caracas (Cruce y adición)
    try:
        with open(archivo_ccs, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                ean_limpio = limpiar_ean(row.get('ean', ''))
                llave = generar_llave(row, ean_limpio)
                
                if llave in productos_unicos:
                    # Actualizamos disponibilidad y precios de Caracas si ya existía
                    productos_unicos[llave]['disponibilidad'] = 'ambas'
                    productos_unicos[llave]['price_base_bs_ccs'] = row.get('price_base_bs', '')
                    productos_unicos[llave]['price_final_bs_ccs'] = row.get('price_final_bs', '')
                    productos_unicos[llave]['price_base_ref_ccs'] = row.get('price_base_ref', '')
                    productos_unicos[llave]['price_final_ref_ccs'] = row.get('price_final_ref', '')
                    
                    # Si el producto de Carabobo no tenía imagen pero el de Caracas sí, la actualizamos
                    if productos_unicos[llave].get('image_url') in ['N/A', ''] and row.get('image_url'):
                        productos_unicos[llave]['image_url'] = row.get('image_url').strip()
                else:
                    # Producto exclusivo de Caracas
                    productos_unicos[llave] = {
                        'ean': ean_limpio,
                        'name': row.get('name', '').strip(),
                        'brand': row.get('brand', '').strip(),
                        'department': row.get('department', '').strip(),
                        'category': row.get('category', '').strip(),
                        'image_url': row.get('image_url', 'N/A').strip(), # <-- Imagen añadida
                        'disponibilidad': 'caracas',
                        'price_base_bs_val': '',
                        'price_final_bs_val': '',
                        'price_base_ref_val': '',
                        'price_final_ref_val': '',
                        'price_base_bs_ccs': row.get('price_base_bs', ''),
                        'price_final_bs_ccs': row.get('price_final_bs', ''),
                        'price_base_ref_ccs': row.get('price_base_ref', ''),
                        'price_final_ref_ccs': row.get('price_final_ref', '')
                    }
        print(f"  -> {archivo_ccs} procesado (Cruce realizado).")
    except FileNotFoundError:
        print(f"[!] No se encontró el archivo: {archivo_ccs}")

    if not productos_unicos:
        print("[!] No hay datos para exportar.")
        return

    # 3. Filtrar y Exportar a CSV separados
    print(f"[*] Separando productos por validación de EAN...")
    
    # Se añade image_url a las columnas finales
    columnas_finales = [
        'ean', 'name', 'brand', 'department', 'category', 'image_url', 'disponibilidad',
        'price_base_bs_val', 'price_final_bs_val', 'price_base_ref_val', 'price_final_ref_val',
        'price_base_bs_ccs', 'price_final_bs_ccs', 'price_base_ref_ccs', 'price_final_ref_ccs'
    ]
    
    contador_validos = 0
    contador_faltantes = 0
    
    with open(archivo_validos, mode='w', newline='', encoding='utf-8') as f_val, \
         open(archivo_faltantes, mode='w', newline='', encoding='utf-8') as f_falt:
        
        writer_val = csv.DictWriter(f_val, fieldnames=columnas_finales)
        writer_falt = csv.DictWriter(f_falt, fieldnames=columnas_finales)
        
        writer_val.writeheader()
        writer_falt.writeheader()
        
        for producto in productos_unicos.values():
            if validar_ean(producto['ean']):
                writer_val.writerow(producto)
                contador_validos += 1
            else:
                writer_falt.writerow(producto)
                contador_faltantes += 1
                
    print(f"[+] ¡Proceso completado exitosamente!")
    print(f"  -> {contador_validos} productos válidos guardados en '{archivo_validos}'")
    print(f"  -> {contador_faltantes} productos irregulares guardados en '{archivo_faltantes}'")

if __name__ == "__main__":
    ARCHIVO_CARABOBO = 'C:\\Users\\USUARIO\\Documents\\1. Work\\Kuantip\\scripts\\kalea ✅\\kalea_carabobo.csv'
    ARCHIVO_CARACAS = 'C:\\Users\\USUARIO\\Documents\\1. Work\\Kuantip\\scripts\\kalea ✅\\kalea_caracas.csv'
    ARCHIVO_VALIDOS = 'prods_kalea.csv'
    ARCHIVO_FALTANTES = 'prods_ean_faltantes_kalea.csv'
    
    unificar_y_filtrar_catalogos(ARCHIVO_CARABOBO, ARCHIVO_CARACAS, ARCHIVO_VALIDOS, ARCHIVO_FALTANTES)