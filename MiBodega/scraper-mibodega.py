import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import re
import requests
import concurrent.futures

def iniciar_navegador():
    print("Iniciando navegador Thorium (undetected_chromedriver)...")
    opciones = uc.ChromeOptions()
    opciones.add_argument('--no-sandbox')
    
    ruta_navegador = r"C:\Users\USUARIO\AppData\Local\Thorium\Application\thorium.exe"
    
    try:
        driver = uc.Chrome(
            options=opciones, 
            browser_executable_path=ruta_navegador, 
            version_main=138
        )
        return driver
    except Exception as e:
        print(f"Error fatal al iniciar el driver: {e}")
        return None

def extraer_sku_individual(producto):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
    }
    
    try:
        res = requests.get(producto['Enlace Producto'], headers=headers, timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            
            sku_tag = soup.find(class_='sku')
            if sku_tag:
                producto['SKU / Barcode'] = sku_tag.text.strip()
    except Exception as e:
        pass
        
    return producto

def scrape_mibodega_global(driver, max_pages=None):
    productos_basicos = []
    page = 1
    
    print("\n--- FASE 1: Extrayendo Catálogo Principal ---")
    while True:
        url = f"https://mibodega.com.ve/productos/page/{page}/?alg_wc_products_per_page=100"
        print(f"Cargando página {page}: {url}")
        
        driver.get(url)
        time.sleep(4) 
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # CORRECCIÓN: Usamos 'type-product' en lugar de 'product-small' para evitar duplicados del HTML
        product_cards = soup.find_all('div', class_=re.compile(r'type-product'))
        
        if not product_cards:
            print("No se encontraron más productos. Final de la paginación alcanzado.")
            break
            
        for card in product_cards:
            enlace_tag = card.find('a', class_=re.compile(r'woocommerce-LoopProduct-link'))
            if not enlace_tag:
                enlace_tag = card.find('a')
            
            enlace_producto = enlace_tag.get('href') if enlace_tag else None
            if not enlace_producto:
                continue
                
            name_tag = card.find('p', class_='name')
            nombre = name_tag.text.strip() if name_tag else "N/A"
            
            classes = card.get('class', [])
            categorias_crudas = [c.replace('product_cat-', '').replace('-', ' ').title() for c in classes if c.startswith('product_cat-')]
            categorias = ", ".join(categorias_crudas) if categorias_crudas else "N/A"
            
            precio_final = None
            price_tag = card.select_one('.price-wrapper .amount bdi')
            if price_tag:
                price_text = price_tag.text.replace('$', '').replace(',', '').strip()
                match = re.search(r'(\d+(?:\.\d+)?)', price_text)
                if match:
                    try:
                        precio_final = float(match.group(1))
                    except ValueError:
                        pass
            
            imagen_url = "N/A"
            img_tag = card.find('img')
            if img_tag:
                imagen_url = img_tag.get('data-lazy-src') or img_tag.get('src', 'N/A')
                imagen_url = re.sub(r'-\d+x\d+\.(jpg|png|webp)$', r'.\1', imagen_url)
                
            productos_basicos.append({
                'SKU / Barcode': "N/A", 
                'Nombre': nombre,
                'Categorias': categorias,
                'Precio Final REF': precio_final,
                'Imagen URL': imagen_url,
                'Enlace Producto': enlace_producto
            })
            
        if max_pages and page >= max_pages:
            print(f"Límite de {max_pages} páginas alcanzado.")
            break
            
        page += 1

    print(f"\n[*] Catálogo recolectado: {len(productos_basicos)} productos únicos identificados.")
    print("\n--- FASE 2: Extrayendo SKUs Internos (Multithreading) ---")
    
    productos_completos = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        resultados = executor.map(extraer_sku_individual, productos_basicos)
        
        for i, prod_procesado in enumerate(resultados, 1):
            productos_completos.append(prod_procesado)
            if i % 50 == 0 or i == len(productos_basicos):
                print(f"  -> {i}/{len(productos_basicos)} productos inspeccionados...")
                
    return productos_completos

if __name__ == "__main__":
    driver = iniciar_navegador()
    
    if driver:
        try:
            todos_los_datos = scrape_mibodega_global(driver) 
            
            if todos_los_datos:
                for p in todos_los_datos:
                    p.pop('Enlace Producto', None)
                    
                df = pd.DataFrame(todos_los_datos)
                
                # CORRECCIÓN EXTRA: Forzar la eliminación de duplicados exactos usando pandas por si acaso
                df = df.drop_duplicates(subset=['Nombre'])
                
                nombre_excel = "mibodega_maestro_total.xlsx"
                try:
                    df.to_excel(nombre_excel, index=False)
                    print(f"\n¡Éxito total! {len(df)} productos exportados a {nombre_excel}.")
                except ImportError:
                    nombre_csv = "mibodega_maestro_total.csv"
                    df.to_csv(nombre_csv, index=False, sep=';', decimal=',')
                    print(f"\n¡Éxito total! Exportado a {nombre_csv} (instala openpyxl para exportar a excel).")
            else:
                print("\nNo se encontraron datos.")
                
        finally:
            driver.quit()