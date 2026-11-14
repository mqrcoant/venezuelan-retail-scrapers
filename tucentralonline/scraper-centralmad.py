import json
import pandas as pd
import time
import os
import random
from pathlib import Path
from playwright.sync_api import sync_playwright

CHECKPOINT = Path(__file__).resolve().parent.parent / 'logs' / 'tucentral_checkpoint.jsonl'

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
    df['SKU'] = df['SKU'].fillna('').astype(str)
    df['_clave'] = df['SKU'].where(df['SKU'].ne(''), df['URL del Producto'].fillna(''))
    vacias = df['_clave'].eq('')
    df.loc[vacias, '_clave'] = 'fila_' + df.index[vacias].astype(str)
    df = df.drop_duplicates(subset=['_clave', 'Sede'], keep='first')
    df_agrupado = df.groupby('_clave', as_index=False).agg({
        'SKU': 'first',
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
    df_agrupado.drop(columns=['_clave'], inplace=True)
    df_agrupado.to_excel(nombre_archivo, index=False)
    print(f"\n💾 [AUTOGUARDADO] Archivo actualizado: '{nombre_archivo}' con {len(df_agrupado)} productos únicos.")
    return df.drop(columns=['_clave'])

def main():
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    if os.environ.get('TUCENTRAL_RESUME') != '1':
        CHECKPOINT.unlink(missing_ok=True)
    paginas_guardadas = {}
    if CHECKPOINT.exists():
        with CHECKPOINT.open(encoding='utf-8') as archivo:
            for linea in archivo:
                registro = json.loads(linea)
                paginas_guardadas[registro['clave']] = registro['productos']
    print(f'Reanudando con {len(paginas_guardadas)} páginas guardadas', flush=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        try:
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1280, 'height': 720}
            )
            page = context.new_page()
            for slug_sede, nombre_sede in SEDES.items():
                print(f'Iniciando sede: {nombre_sede}', flush=True)
                for categoria in CATEGORIAS:
                    page_num = 1
                    while True:
                        clave = f'{slug_sede}|{categoria}|{page_num}'
                        if clave in paginas_guardadas:
                            if not paginas_guardadas[clave]:
                                break
                            page_num += 1
                            continue
                        url = f'https://tucentralonline.com/{slug_sede}/comprar/{categoria}/'
                        if page_num > 1:
                            url += f'page/{page_num}/'
                        respuesta = page.goto(url, wait_until='domcontentloaded', timeout=45000)
                        estado = respuesta.status if respuesta else None
                        if estado == 404 and page_num > 1:
                            tarjetas = 0
                            spans = []
                        else:
                            if estado != 200:
                                raise RuntimeError(f'TuCentral devolvió HTTP {estado} en {url}; se conserva el checkpoint')
                            if page.locator('text=Wordfence').count() or page.locator('text=Tu acceso a este sitio ha sido limitado').count():
                                raise RuntimeError(f'Wordfence bloqueó {url}; se conserva el checkpoint')
                            tarjetas = page.locator('li.product').count()
                            spans = page.locator('span.gtm4wp_productdata').evaluate_all(
                                "els => els.map(el => el.getAttribute('data-gtm4wp_product_data'))"
                            )
                        if not tarjetas:
                            paginas_guardadas[clave] = []
                            with CHECKPOINT.open('a', encoding='utf-8') as archivo:
                                archivo.write(json.dumps({'clave': clave, 'productos': []}) + '\n')
                            break
                        if len(spans) != tarjetas:
                            raise RuntimeError(f'{len(spans)} datos para {tarjetas} tarjetas en {url}')
                        productos_pagina = []
                        for raw in spans:
                            data = json.loads(raw or '{}')
                            productos_pagina.append({
                                'SKU': str(data.get('sku') or ''),
                                'Nombre': data.get('item_name'),
                                'Categoría 1': data.get('item_category'),
                                'Categoría 2': data.get('item_category2'),
                                'Precio': float(data.get('price') or 0),
                                'Stock Level': int(data.get('stocklevel') or 0),
                                'Estado de Stock': data.get('stockstatus'),
                                'URL del Producto': data.get('productlink'),
                                'Sede': nombre_sede
                            })
                        paginas_guardadas[clave] = productos_pagina
                        with CHECKPOINT.open('a', encoding='utf-8') as archivo:
                            archivo.write(json.dumps({'clave': clave, 'productos': productos_pagina}, ensure_ascii=False) + '\n')
                        print(f'{nombre_sede} | {categoria} | página {page_num}: {len(productos_pagina)}', flush=True)
                        page_num += 1
                        time.sleep(random.uniform(3.5, 7.5))
        finally:
            browser.close()

    # Procesamiento final
    todos_los_productos = [producto for pagina in paginas_guardadas.values() for producto in pagina]
    if todos_los_productos:
        sedes_con_productos = {producto['Sede'] for producto in todos_los_productos}
        if len(sedes_con_productos) != len(SEDES):
            raise RuntimeError(f'Solo hay datos de {len(sedes_con_productos)} de {len(SEDES)} sedes')
        salida_dir = Path(__file__).resolve().parents[1] / 'finales' / 'tucentralonline'
        salida_dir.mkdir(parents=True, exist_ok=True)
        detalle = procesar_y_guardar_excel(todos_los_productos, str(salida_dir / 'inventario_consolidado_tucentral.xlsx'))
        detalle.to_excel(salida_dir / 'inventario_por_sede_tucentral.xlsx', index=False)
        CHECKPOINT.unlink(missing_ok=True)
        print("\n🎉 ¡PROCESO COMPLETADO EXITOSAMENTE!")
    else:
        raise RuntimeError('No se extrajeron datos')

if __name__ == "__main__":
    main()
