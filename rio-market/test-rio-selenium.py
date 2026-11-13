import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import re
import logging

# 1. Configuración de Logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("test_scraper.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Diccionario maestro en memoria (Llave: EAN) para evitar duplicados
productos_dict = {}

def iniciar_navegador():
    logging.info("Iniciando navegador Thorium en modo oculto (Headless)...")
    opciones = uc.ChromeOptions()
    opciones.add_argument('--no-sandbox')
    
    # Activar el nuevo modo headless (menos detectable)
    opciones.add_argument('--headless=new')
    
    # CRÍTICO: Forzar resolución para que la UI no colapse a modo móvil
    opciones.add_argument('--window-size=1920,1080')
    
    ruta_navegador = r"C:\Users\USUARIO\AppData\Local\Thorium\Application\thorium.exe" #[cite: 1]
    
    try:
        driver = uc.Chrome(
            options=opciones, 
            browser_executable_path=ruta_navegador, 
            version_main=138 #[cite: 1]
        )
        logging.info("Navegador iniciado correctamente.")
        return driver
    except Exception as e:
        logging.error(f"Error fatal al iniciar el driver: {e}")
        return None

def cambiar_sede(driver, nombre_sede):
    logging.info(f"Intentando cambiar a la sede: {nombre_sede}")
    try:
        # 1. Desplegar el modal (Clic en el contenedor de la sucursal)
        btn_header = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Recoger en:') or contains(text(), 'Retirar en:')]/parent::* | //i[contains(@class, 'prev-arrow') and contains(@class, 'ph-caret-down')]"))
        )
        driver.execute_script("arguments[0].click();", btn_header)
        logging.debug("Modal de sucursales abierto.")
        time.sleep(2)

        # 2. Seleccionar modalidad "En tienda" (Pick and Collect)
        try:
            # Escenario A: Modal de primera visita (Radio button grande)
            opcion_tienda_inicial = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.XPATH, "//div[@data-testid='opmodel-form-option-pick_and_collect']//label"))
            )
            driver.execute_script("arguments[0].click();", opcion_tienda_inicial)
            time.sleep(1)
            
            # Hacer clic en "Siguiente" en el modal inicial
            try:
                btn_siguiente = driver.find_element(By.XPATH, "//button[contains(., 'Siguiente')]")
                driver.execute_script("arguments[0].click();", btn_siguiente)
                time.sleep(1)
            except Exception:
                pass

        except Exception:
            # Escenario B: Modal de visitas posteriores (Botón tipo tab)
            try:
                btn_tab_tienda = driver.find_element(By.XPATH, "//input[@data-testid='opmodel-button-pick_and_collect']/parent::span")
                driver.execute_script("arguments[0].click();", btn_tab_tienda)
                time.sleep(1)
            except Exception:
                logging.debug("Opción 'En tienda' no encontrada o ya seleccionada.")

        # 3. Si ya hay una tienda seleccionada (Escenario B), hacer clic en "Cambiar"
        try:
            btn_cambiar = driver.find_element(By.XPATH, "//button[@data-testid='change-store-button'] | //span[text()='Cambiar']/ancestor::button")
            driver.execute_script("arguments[0].click();", btn_cambiar)
            time.sleep(1)
        except Exception:
            pass # Es la primera visita y la lista de tiendas ya debería estar visible

        # 4. Llenar Estado y Ciudad (Componentes Ant Design)
        try:
            input_estado = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.ID, "PickanCollectForm_state"))
            )
            input_estado.send_keys(Keys.CONTROL + "a")
            input_estado.send_keys(Keys.DELETE)
            input_estado.send_keys("Distrito Capital")
            time.sleep(1) 
            input_estado.send_keys(Keys.ENTER)
            time.sleep(1)
            
            input_ciudad = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.ID, "PickanCollectForm_city"))
            )
            input_ciudad.send_keys(Keys.CONTROL + "a")
            input_ciudad.send_keys(Keys.DELETE)
            input_ciudad.send_keys("Caracas")
            time.sleep(1)
            input_ciudad.send_keys(Keys.ENTER)
            time.sleep(2) 
        except Exception:
            logging.debug("Formulario de estado/ciudad no requerido o no encontrado en esta vista.")

        # 5. Seleccionar la tienda específica
        tienda_label = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, f"//span[@class='store-card__title' and contains(text(), '{nombre_sede}')]/ancestor::label"))
        )
        driver.execute_script("arguments[0].click();", tienda_label)
        logging.info(f"Clic realizado en la sede {nombre_sede}.")

        # 6. Esperar a que la página recargue el contexto con los precios locales
        time.sleep(5)
        return True

    except Exception as e:
        logging.error(f"Error en el flujo de cambiar_sede para {nombre_sede}: {e}")
        return False

def scrape_prueba_categoria(driver, category_url, sede_actual, max_productos=3):
    logging.info(f"Scrapeando URL: {category_url} en sede {sede_actual}")
    driver.get(category_url)
    
    # Reemplazar time.sleep(4) por una espera inteligente
    try:
        # Espera hasta 10 segundos a que aparezca al menos un producto en el DOM
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/p/')]"))
        )
        time.sleep(1) # Breve pausa adicional para asegurar que las imágenes y precios terminen de pintar
    except Exception:
        logging.debug("No se cargaron productos en 10s. Es probable que la categoría esté vacía en esta sede.")
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    product_links = soup.find_all('a', href=re.compile(r'/p/'))
    
    if not product_links:
        logging.warning("No se encontraron productos en esta página.")
        return

    productos_extraidos = 0
    fecha_extraccion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    vistos_pagina = set()
    
    for link in product_links:
        if productos_extraidos >= max_productos:
            logging.info(f"Se alcanzó el límite de {max_productos} productos para esta prueba.")
            break

        href = link.get('href', '')
        if href in vistos_pagina:
            continue
        vistos_pagina.add(href)
        
        ean_match = re.search(r'-(\d+)$', href)
        ean = ean_match.group(1) if ean_match else "N/A"
        
        if ean in productos_dict:
            logging.debug(f"Producto duplicado (EAN: {ean}). Añadiendo sede {sede_actual}.")
            productos_dict[ean]['Sedes Disponibles'].add(sede_actual)
            productos_extraidos += 1
            continue
        
        nombre_tag = link.find('h3')
        nombre = nombre_tag.text.strip() if nombre_tag else "N/A"
        
        precio_paquete = None
        textos_precios = re.findall(r'REF\s*(\d+(?:,\d+)?)', link.text)
        
        if textos_precios:
            try:
                precios_float = [float(p.replace(',', '.')) for p in textos_precios]
                precio_paquete = min(precios_float) 
            except ValueError:
                pass

        precio_kg = None
        pum_tag = link.find('p', class_=lambda c: c and 'prod__pum' in c)
        if pum_tag:
            match_pum = re.search(r'kg a REF\s*(\d+(?:,\d+)?)', pum_tag.text)
            if match_pum:
                try:
                    precio_kg = float(match_pum.group(1).replace(',', '.'))
                except ValueError:
                    pass
        
        img_tag = link.find('img')
        imagen_url = img_tag.get('src', 'N/A') if img_tag else "N/A"
        
        productos_dict[ean] = {
            'EAN': ean,
            'Nombre': nombre,
            'Precio Paquete REF': precio_paquete,
            'Precio por KG REF': precio_kg,
            'Imagen URL': imagen_url,
            'Sedes Disponibles': {sede_actual},
            'Fecha de Extraccion': fecha_extraccion
        }
        
        logging.info(f"Extraído: {nombre} | EAN: {ean} | REF: {precio_paquete}")
        productos_extraidos += 1

if __name__ == "__main__":
    sedes_caracas = [
        "Río Supermarket El Paraíso",
        "Río Supermarket La Candelaria",
        "Río Supermarket Lomas del Sol",
        "Río Supermarket Cigarral - El Hatillo",
        "Río Supermarket El Marqués",
        "Río Supermarket Los Campitos",
        "Río Supermarket El Recreo"
    ] 
    
    url_prueba = 'https://www.riomarket.com/ca/carnes-y-refrigerados/9'
    
    driver = iniciar_navegador()
    
    if driver:
        try:
            logging.info("Navegando a la página principal para establecer cookies iniciales.")
            driver.get("https://www.riomarket.com/")
            time.sleep(3)
            
            for sede in sedes_caracas:
                exito = cambiar_sede(driver, sede)
                if exito:
                    scrape_prueba_categoria(driver, url_prueba, sede, max_productos=3)
                else:
                    logging.warning(f"Saltando extracción para {sede} debido a error en cambio.")
                    
        finally:
            logging.info("Cerrando navegador.")
            driver.quit()
            
        if productos_dict:
            logging.info("Procesando datos para exportación...")
            for ean, data in productos_dict.items():
                data['Sedes Disponibles'] = ", ".join(data['Sedes Disponibles'])
                
            df = pd.DataFrame(list(productos_dict.values()))
            
            nombre_excel = "prueba_sedes_riomarket.xlsx"
            df.to_excel(nombre_excel, index=False)
            logging.info(f"¡Prueba finalizada! Datos exportados a {nombre_excel}. Total de SKUs únicos: {len(productos_dict)}")
        else:
            logging.warning("No se encontraron datos para exportar.")