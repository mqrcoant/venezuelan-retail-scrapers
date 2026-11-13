import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import re

def iniciar_navegador():
    print("Iniciando navegador Thorium (undetected_chromedriver)...")
    opciones = uc.ChromeOptions()
    
    # Mantenemos las opciones de tu script de referencia
    # opciones.add_argument('--headless') 
    opciones.add_argument('--no-sandbox')
    
    # Tu ruta exacta a Thorium
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

def scrape_riomarket_category(driver, category_url, max_pages=None):
    productos = []
    page = 1
    
    # NUEVO: Extraemos el nombre de la categoría desde la URL
    # Ej: de '.../ca/carnes-y-refrigerados/9' extrae 'carnes-y-refrigerados'
    categoria_slug = category_url.split('/')[-2]
    # Lo formateamos bonito: 'Carnes Y Refrigerados'
    categoria_nombre = categoria_slug.replace('-', ' ').title() 
    
    while True:
        url = f"{category_url}?currentPage={page}"
        print(f"Cargando página: {url}")
        
        driver.get(url)
        
        # Le damos 5 segundos a Thorium para que Next.js ejecute su JavaScript 
        time.sleep(5) 
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Buscamos los enlaces de productos
        product_links = soup.find_all('a', href=re.compile(r'/p/'))
        
        if not product_links:
            print("No se encontraron productos en esta página. Es posible que sea el final de la categoría.")
            break
            
        fecha_extraccion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        vistos = set()
        
        for link in product_links:
            href = link.get('href', '')
            if href in vistos:
                continue
            vistos.add(href)
            
            # 1. EAN
            ean_match = re.search(r'-(\d+)$', href)
            ean = ean_match.group(1) if ean_match else "N/A"
            
            # 2. Nombre
            nombre_tag = link.find('h3')
            nombre = nombre_tag.text.strip() if nombre_tag else "N/A"
            
            # 3. Precios
            precio_paquete = None
            precio_kg = None
            
            # A. Extraer precio del paquete (Ej: REF 2,69)
            precio_tag = link.find('p', class_=lambda c: c and 'base__price' in c)
            if not precio_tag:
                # Respaldo por si cambia la clase
                precio_tag = link.find(string=re.compile(r'REF\s*\d+,\d+'))
            
            if precio_tag:
                txt = precio_tag.text if hasattr(precio_tag, 'text') else str(precio_tag)
                match = re.search(r'REF\s*(\d+(?:,\d+)?)', txt)
                if match:
                    try:
                        precio_paquete = float(match.group(1).replace(',', '.'))
                    except ValueError:
                        pass

            # B. Extraer precio real por KG (Ej: 0.2 kg (kg a REF 13,45))
            pum_tag = link.find('p', class_=lambda c: c and 'prod__pum' in c)
            if pum_tag:
                txt_pum = pum_tag.text
                match_pum = re.search(r'kg a REF\s*(\d+(?:,\d+)?)', txt_pum)
                if match_pum:
                    try:
                        precio_kg = float(match_pum.group(1).replace(',', '.'))
                    except ValueError:
                        pass
            
            # 4. Imagen
            img_tag = link.find('img')
            imagen_url = img_tag.get('src', 'N/A') if img_tag else "N/A"
            
            # NUEVO: Añadimos la categoría extraída a nuestro diccionario
            productos.append({
                'EAN': ean,
                'Nombre': nombre,
                'Categoria': categoria_nombre, # <--- AQUI SE INCLUYE
                'Precio Paquete REF': precio_paquete,
                'Precio por KG REF': precio_kg,
                'Imagen URL': imagen_url,
                'Fecha de Extraccion': fecha_extraccion
            })
            
        # Paginación
        next_button = soup.find('li', class_='ant-pagination-next')
        if next_button and next_button.get('aria-disabled') == 'true':
            print("Última página alcanzada.")
            break
            
        if max_pages and page >= max_pages:
            print(f"Límite de {max_pages} páginas alcanzado.")
            break
            
        page += 1
        
    return productos

if __name__ == "__main__":
    categorias_urls = [
        'https://www.riomarket.com/ca/carnes-y-refrigerados/9',
        'https://www.riomarket.com/ca/cesta-basica/11',
        'https://www.riomarket.com/ca/cuidado-personal/3',
        'https://www.riomarket.com/ca/frulever/12',
        'https://www.riomarket.com/ca/hogar/6',
        'https://www.riomarket.com/ca/bebidas/2',
        'https://www.riomarket.com/ca/licores/7',
        'https://www.riomarket.com/ca/dulces-y-snacks/4',
        'https://www.riomarket.com/ca/frutos-secos-y-otros/13',
        'https://www.riomarket.com/ca/salud-y-bienestar/10',
        'https://www.riomarket.com/ca/bebes/1',
        'https://www.riomarket.com/ca/mascotas/8',
        'https://www.riomarket.com/ca/eventuales/5',
        'https://www.riomarket.com/ca/super-ofertas/14',
        'https://www.riomarket.com/ca/electrodomesticos/15'
    ]
    
    todos_los_datos = []
    driver = iniciar_navegador()
    
    if driver:
        try:
            for url in categorias_urls:
                print(f"\n--- Iniciando extracción para: {url} ---")
                datos_cat = scrape_riomarket_category(driver, url) 
                todos_los_datos.extend(datos_cat)
        finally:
            driver.quit()
            
        if todos_los_datos:
            # Ahora el DataFrame incluirá automáticamente la nueva columna
            df = pd.DataFrame(todos_los_datos)
            
            # Reorganizamos las columnas para que la categoría salga al principio, después del EAN y Nombre
            columnas = ['EAN', 'Nombre', 'Categoria', 'Precio Paquete REF', 'Precio por KG REF', 'Imagen URL', 'Fecha de Extraccion']
            df = df[columnas]
            
            nombre_excel = "riomarket_maestro_total.xlsx"
            try:
                df.to_excel(nombre_excel, index=False)
                print(f"\n¡Éxito total! Datos exportados a {nombre_excel}.")
            except ImportError:
                df.to_csv("riomarket_maestro_total.csv", index=False, sep=';', decimal=',')
                print("\nExportado a CSV (instala openpyxl para exportar a excel).")
        else:
            print("\nNo se encontraron datos.")