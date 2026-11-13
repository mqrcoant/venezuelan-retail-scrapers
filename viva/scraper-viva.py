import asyncio
import aiohttp
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import pandas as pd

# ==========================================
# FASE 1: OBTENER SESIÓN CON PLAYWRIGHT
# ==========================================
async def get_session_cookies_and_headers(city_name="Caracas"):
    print(f"[*] Iniciando Playwright para capturar sesión en {city_name}...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        await page.goto("https://vivaenlinea.com/")
        
        try:
            await page.wait_for_selector("a#opener_geo_maps_location_dialog_46577", timeout=5000)
            await page.click("a#opener_geo_maps_location_dialog_46577")
            await page.get_by_text(city_name, exact=True).click()
            await page.wait_for_load_state("networkidle")
        except Exception:
            print("[!] No se detectó el modal o ya estaba seleccionada la ciudad.")

        cookies = await context.cookies()
        ua = await page.evaluate("navigator.userAgent")
        aiohttp_cookies = {cookie['name']: cookie['value'] for cookie in cookies}
        
        await browser.close()
        print("[+] Sesión capturada con éxito.")
        return aiohttp_cookies, ua

# ==========================================
# FASE 2: EXTRACCIÓN CON AIOHTTP + BS4
# ==========================================
async def fetch_product_detail(session, sem, product):
    """Entra a la página de detalle SOLO para extraer el código de artículo."""
    if not product.get("url"):
        return product

    async with sem:
        try:
            async with session.get(product["url"]) as response:
                html = await response.text()
                soup = BeautifulSoup(html, "lxml")
                
                # Extraer Código de artículo
                codigo_label = soup.find(lambda tag: tag.name == "span" and "Cod. artículo:" in tag.text)
                if codigo_label:
                    parent = codigo_label.parent
                    codigo_val = parent.find("span", class_="ty-control-group__item")
                    product["codigo_articulo"] = codigo_val.text.strip() if codigo_val else "N/A"
                else:
                    product["codigo_articulo"] = "N/A"
                
        except Exception as e:
            print(f"[!] Error al extraer detalle de {product['url']}: {e}")
            product["codigo_articulo"] = "ERROR"
            
    return product

async def scrape_category(session, cat_url, nombre_categoria, sem):
    """Pagina a través de la categoría y etiqueta cada producto con su sección."""
    page_num = 1
    products = []
    
    while True:
        url = f"{cat_url}page-{page_num}/?items_per_page=128&result_ids=pagination_contents&is_ajax=1"
        
        async with session.get(url) as response:
            try:
                data = await response.json()
            except Exception:
                print(f"[!] Error decodificando JSON en {url}")
                break
            
            html_content = data.get('html', {}).get('pagination_contents', '')
            
            if not html_content or 'ty-column4' not in html_content:
                break
                
            soup = BeautifulSoup(html_content, "lxml")
            cards = soup.select(".ty-column4")
            
            if not cards:
                break
                
            for card in cards:
                title_el = card.select_one("a.product-title")
                price_el = card.select_one("span[id^='sec_discounted_price_']")
                img_el = card.select_one("img.ty-pict")
                
                if not title_el:
                    continue
                    
                prod_data = {
                    "categoria": nombre_categoria,
                    "nombre": title_el.text.strip(),
                    "precio_final": price_el.text.strip() if price_el else None,
                    "codigo_articulo": None,  # Se llenará en la extracción de detalle
                    "url": title_el.get("href"),
                    "imagen": img_el.get("src") or img_el.get("data-src") if img_el else None
                }
                products.append(prod_data)
            
            print(f"  -> {nombre_categoria} - Página {page_num}: {len(cards)} productos extraídos.")
            page_num += 1

    # Extraer Código de Artículo concurrentemente
    tasks = [fetch_product_detail(session, sem, p) for p in products]
    detailed_products = await asyncio.gather(*tasks)
    
    return detailed_products

async def main():
    cookies, user_agent = await get_session_cookies_and_headers("Caracas")
    
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    # Diccionario de URLs principales con su nombre de categoría legible
    categorias_principales = {
        "Fruver": "https://vivaenlinea.com/alimentos/frutas-y-vegetales/",
        "Alimentos Frescos": "https://vivaenlinea.com/alimentos/",
        "Refrigerados": "https://vivaenlinea.com/alimentos/refrigerados/",
        "Víveres": "https://vivaenlinea.com/alimentos/viveres/",
        "Licores": "https://vivaenlinea.com/licores/",
        "Snacks": "https://vivaenlinea.com/alimentos/snaks-y-frutos-secos/",
        "Cuidado Personal": "https://vivaenlinea.com/cuidado-personal-es/",
        "Hogar": "https://vivaenlinea.com/hogar-es/",
        "Mascotas": "https://vivaenlinea.com/mascotas/",
        "Limpieza": "https://vivaenlinea.com/limpieza/"
    }
    
    async with aiohttp.ClientSession(cookies=cookies, headers=headers) as session:
        sem = asyncio.Semaphore(20)
        todas_las_categorias_tasks = []
        
        for nombre, url in categorias_principales.items():
            todas_las_categorias_tasks.append(scrape_category(session, url, nombre, sem))
            
        resultados_por_categoria = await asyncio.gather(*todas_las_categorias_tasks)
        catalogo_maestro = [producto for sublist in resultados_por_categoria for producto in sublist]
        
        print(f"\n[+] Proceso finalizado. Total de productos extraídos: {len(catalogo_maestro)}")
        
        # Exportar a Excel con Pandas
        df = pd.DataFrame(catalogo_maestro)
        df.to_excel("catalogo_viva.xlsx", index=False, engine='openpyxl')
        print("[+] Archivo 'catalogo_viva.xlsx' generado con éxito.")

if __name__ == "__main__":
    asyncio.run(main())