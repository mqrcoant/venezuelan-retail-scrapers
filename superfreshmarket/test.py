import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import time

def diagnosticar_con_navegador():
    print("Iniciando navegador fantasma con version_main fija...")
    
    opciones = uc.ChromeOptions()
    opciones.add_argument('--headless') 
    opciones.add_argument('--no-sandbox')
    
    # REEMPLAZA CON LA RUTA REAL A TU NAVEGADOR EN WINDOWS
    ruta_navegador = r"C:\Users\USUARIO\AppData\Local\Thorium\Application\thorium.exe"
    
    try:
        # Le indicamos explicitamente version_main=138 para forzar el match
        driver = uc.Chrome(
            options=opciones,
            browser_executable_path=ruta_navegador,
            version_main=138
        )
        
        url = "https://superfreshmarket.com.ve/categoria-producto/viveres/"
        print(f"Navegando a: {url}...")
        
        driver.get(url)
        print("Esperando 8 segundos para que el JS resuelva el desafío del firewall...")
        time.sleep(8)
        
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        titulo = soup.title.text.strip() if soup.title else "Sin título"
        print(f"Título detectado: {titulo}")
        
        tarjetas = soup.find_all('li', class_='type-product')
        print(f"Tarjetas de producto encontradas: {len(tarjetas)}")
        
        if len(tarjetas) > 0:
            print("\n¡Éxito! El firewall permitió el acceso y detectó los productos.")
            
    except Exception as e:
        print(f"Error crítico del driver: {e}")
    finally:
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    diagnosticar_con_navegador()