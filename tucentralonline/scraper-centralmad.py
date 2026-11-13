from playwright.sync_api import sync_playwright
import json
import pandas as pd
import time
import random
import os

SEDES = {
    'Av-Presidente-Medina-02': 'Av Presidente Medina',
    'Plaza-Las-Americas-03': 'Plaza Las Américas',
    'Los_Ruices_04': 'Los Ruices',
    'Santa-Marta-06': 'Santa Marta',
    'Chacaito-07': 'Chacaito',
    'Bello-Monte-08': 'Bello Monte',
    'el-marques-09': 'El Marques',
    'lomas-del-avila-10': 'Lomas del Avila',
    'San-Jose-11': 'San José',
    'La-Boyera-18': 'La Boyera',
    'Catia-19': 'Catia',
    'altos-mirandinos-23': 'Altos Mirandinos',
    'Montalban-25': 'Montalbán',
    'Bello-Campo-43': 'Bello Campo',
    'La-Lagunita-44': 'La Lagunita',
    'La-Alameda-50': 'La Alameda',
    'Manzanares_52': 'Manzanares',
    'Maiquetia-53': 'Maiquetia'
}

CATEGORIAS = [
    # VÍVERES
    "viveres/alimento-infantil", "viveres/bebidas", "viveres/complementos-alimenticios",
    "viveres/enlatados", "viveres/harinas", "viveres/lacteos-y-derivados",
    "viveres/panes-y-cereales", "viveres/salsas-aderezos-condimentos-y-sopas",
    "viveres/arroz-y-granos", "viveres/cafe-y-endulzantes", "viveres/delicateses-y-encurtidos",
    "viveres/snacks", "viveres/galletas-golosinas-y-reposteria", "viveres/infusiones",
    "viveres/margarinas-y-aceites", "viveres/pastas", "viveres/untables",

    # REFRIGERADOS
    "refrigerados/carniceria-pescaderia/carnes-aves", "refrigerados/carniceria-pescaderia/pescados-maricos",
    "refrigerados/charcuteria/bologna-mortadela", "refrigerados/charcuteria/delicateses-refrigeradas",
    "refrigerados/charcuteria/embutidos", "refrigerados/charcuteria/huevos", "refrigerados/charcuteria/jamones",
    "refrigerados/charcuteria/quesos", "refrigerados/charcuteria/salchichas-y-tocinetas",
    "refrigerados/congelados/comidas-congeladas", "refrigerados/congelados/frutas-congeladas",
    "refrigerados/congelados/hielo", "refrigerados/congelados/jugos-concentrados", "refrigerados/congelados/masas",
    "refrigerados/congelados/pasapalos", "refrigerados/congelados/postres", "refrigerados/congelados/pulpas-frutas",
    "refrigerados/congelados/vegetales-congelados", "refrigerados/pasteurizados/bebidas-lacteas",
    "refrigerados/pasteurizados/bebidas-refrescantes", "refrigerados/pasteurizados/derivados-lacteos",
    "refrigerados/pasteurizados/jugos", "refrigerados/pasteurizados/leches", "refrigerados/pasteurizados/yogurt",

    # FRUTAS Y VEGETALES
    "fruteria-y-vegetales/frutas", "fruteria-y-vegetales/vegetales",

    # CUIDADO PERSONAL
    "cuidado-personal/afeitado", "cuidado-personal/colonias", "cuidado-personal/cuidado-bucal",
    "cuidado-personal/cuidado-capilar", "cuidado-personal/cuidado-corporal", "cuidado-personal/cuidado-facial",
    "cuidado-personal/cuidado-infantil", "cuidado-personal/desodorantes", "cuidado-personal/proteccion-femenina",
    "cuidado-personal/proteccion-sanitaria",

    # ARTÍCULOS DE LIMPIEZA
    "articulos-de-limpieza/ambientadores", "articulos-de-limpieza/articulos-p-limpiar",
    "articulos-de-limpieza/cuidado-de-ropa-y-telas", "articulos-de-limpieza/cuidado-vajilla",
    "articulos-de-limpieza/higiene-personal", "articulos-de-limpieza/insecticidas",
    "articulos-de-limpieza/mantenimiento-automotriz", "articulos-de-limpieza/repelentes",

    # LICORES
    "licores/cervezas", "licores/destilados", "licores/licores-dulces", "licores/licores-secos",
    "licores/rones", "licores/vinos-y-espumantes", "licores/whisky", "licores/ready-to-drink",

    # HOGAR Y TEMPORADA
    "hogar-temporada/deporte-y-camping", "hogar-temporada/lenceria",
    "hogar-temporada/mascotas", "hogar-temporada/quincalla"
]

def procesar_y_guardar_excel(datos, nombre_archivo):
    """Agrupa los datos por SKU y guarda el DataFrame en Excel."""
    if not datos:
        return
        
    df = pd.DataFrame(datos)
    df_agrupado = df.groupby('SKU', as_index=False).agg({
        'Nombre': 'first',
        'Categoría 1': 'first',
        'Categoría 2': 'first',
        'Precio': 'first', 
        'Stock Level': 'sum', 
        'Estado de Stock': 'first',
        'URL del Producto': 'first',
        'Sede': lambda x: ', '.join(sorted(set(x))) 
    })
    
    df_agrupado.rename(columns={'Sede': 'Sedes Disponibles'}, inplace=True)
    df_agrupado.to_excel(nombre_archivo, index=False)
    print(f"\n💾 [AUTOGUARDADO] Archivo actualizado: '{nombre_archivo}' con {len(df_agrupado)} productos únicos.")

def main():
    todos_los_productos = []
    bloqueo_detectado = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720}
        )
        pagina_web = context.new_page()

        for slug_sede, nombre_sede in SEDES.items():
            if bloqueo_detectado:
                break
            
            print(f"\n=======================================================")
            print(f"🏢 INICIANDO EXTRACCIÓN EN SEDE: {nombre_sede}")
            print(f"=======================================================")
                
            for categoria in CATEGORIAS:
                if bloqueo_detectado:
                    break
                    
                page_num = 1
                
                while True:
                    url = f"https://tucentralonline.com/{slug_sede}/comprar/{categoria}/"
                    if page_num > 1:
                        url += f"page/{page_num}/"
                        
                    print(f"-> {nombre_sede} | Cat: {categoria} | Pág: {page_num}")
                    
                    try:
                        pagina_web.goto(url, wait_until="domcontentloaded", timeout=45000)
                    except Exception as e:
                        print(f"  ⚠️ Error de red cargando la página: {e}")
                        break
                    
                    # 1. VERIFICACIÓN DE WORDFENCE
                    if pagina_web.locator('text="Wordfence"').count() > 0 or pagina_web.locator('text="Tu acceso a este sitio ha sido limitado"').count() > 0:
                        print("\n🚨 ¡WORDFENCE DETECTADO! Has sido bloqueado temporalmente.")
                        bloqueo_detectado = True
                        break

                    try:
                        # Esperamos a que cargue la estructura de productos
                        pagina_web.wait_for_selector('li.product', timeout=6000)
                    except Exception:
                        print(f"   [!] Fin de paginación o categoría vacía.")
                        break 

                    # 2. EXTRACCIÓN DE DATOS
                    spans = pagina_web.locator('span.gtm4wp_productdata').all()
                    productos_extraidos = 0
                    
                    for span in spans:
                        raw_json = span.get_attribute('data-gtm4wp_product_data')
                        if raw_json:
                            try:
                                data = json.loads(raw_json)
                                todos_los_productos.append({
                                    'SKU': data.get('sku'),
                                    'Nombre': data.get('item_name'),
                                    'Categoría 1': data.get('item_category'),
                                    'Categoría 2': data.get('item_category2'),
                                    'Precio': float(data.get('price', 0)),
                                    'Stock Level': int(data.get('stocklevel', 0) or 0),
                                    'Estado de Stock': data.get('stockstatus'),
                                    'URL del Producto': data.get('productlink'),
                                    'Sede': nombre_sede
                                })
                                productos_extraidos += 1
                            except (json.JSONDecodeError, ValueError):
                                continue
                    
                    print(f"   ✅ Extraídos {productos_extraidos} productos.")
                    page_num += 1
                    
                    # 3. RATE LIMITING
                    retraso = random.uniform(3.5, 7.5)
                    time.sleep(retraso)
            
            # --- GUARDADO PARCIAL AL TERMINAR CADA SEDE ---
            if not bloqueo_detectado:
                procesar_y_guardar_excel(todos_los_productos, 'inventario_parcial_tucentral.xlsx')

        browser.close()

    # Procesamiento final
    if todos_los_productos:
        procesar_y_guardar_excel(todos_los_productos, 'inventario_consolidado_tucentral.xlsx')
        print("\n🎉 ¡PROCESO COMPLETADO EXITOSAMENTE!")
    else:
        print("\n❌ No se extrajeron datos. Revisa si sigues bloqueado.")

if __name__ == "__main__":
    main()