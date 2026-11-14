from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
import pandas as pd
import time
import re
import json
import os
from pathlib import Path

URL = "https://datastudio.google.com/u/0/reporting/f7732857-56bb-4557-8433-6cee0b5cd775/page/V2xOF"
CHECKPOINT = Path(__file__).resolve().parent.parent / 'logs' / 'farmatencion_checkpoint.jsonl'

# Ajustes
WAIT = 45
PAUSA_SELECCION = 1.2
PAUSA_SCROLL = 0.7
MAX_SCROLL_SIN_NUEVOS = 12

def txt(el):
    try:
        return el.text.strip()
    except Exception:
        return ""

def crear_driver():
    opciones = Options()
    opciones.binary_location = r"C:\Users\USUARIO\AppData\Local\Thorium\Application\thorium.exe"
    opciones.add_argument("--no-sandbox")
    opciones.add_argument("--disable-dev-shm-usage")
    opciones.add_argument("--start-maximized")
    opciones.add_argument("--headless=new")
    opciones.add_argument("--window-size=1280,900")

    servicio = Service(
        ChromeDriverManager(driver_version="138.0.7204.303").install()
    )
    driver = webdriver.Chrome(service=servicio, options=opciones)
    driver.set_page_load_timeout(90)
    return driver

def esperar_reporte(driver):
    WebDriverWait(driver, WAIT).until(
        EC.presence_of_element_located(
            (By.XPATH, "//div[contains(@class,'item-single')]")
        )
    )

def obtener_items_visibles(driver):
    """
    Devuelve [(nombre, elemento), ...] de los productos actualmente renderizados.
    Looker Studio virtualiza la lista: no todos los productos existen simultáneamente en el DOM.
    """
    return driver.execute_script("""
        return [...document.querySelectorAll('div.item-single')]
          .map(el => [(el.querySelector('span.dimension-value')?.textContent || '').trim(), el])
          .filter(([nombre]) => nombre);
    """)


def valores_tabla(driver):
    return driver.execute_script("""
        return [...document.querySelectorAll('div.cell span.cell-value')]
          .map(el => (el.textContent || '').trim());
    """)

def buscar_scrollable_ancestor(driver, element):
    """
    Sube por los ancestros del item y localiza el primer contenedor realmente scrollable.
    Esto es mucho más estable que mandar ARROW_DOWN al active_element.
    """
    return driver.execute_script("""
        let el = arguments[0];
        while (el) {
            const s = window.getComputedStyle(el);
            const oy = s.overflowY;
            if ((oy === 'auto' || oy === 'scroll') &&
                el.scrollHeight > el.clientHeight + 5) {
                return el;
            }
            el = el.parentElement;
        }
        return null;
    """, element)

def scroll_lista(driver, scrollbox, cantidad=None):
    if cantidad is None:
        # Avanza algo menos de una pantalla para mantener solapamiento entre lotes.
        cantidad = driver.execute_script(
            "return Math.max(120, Math.floor(arguments[0].clientHeight * 0.72));",
            scrollbox
        )
    antes = driver.execute_script("return arguments[0].scrollTop;", scrollbox)
    driver.execute_script(
        "arguments[0].scrollTop = Math.min(arguments[0].scrollTop + arguments[1], "
        "arguments[0].scrollHeight);",
        scrollbox, cantidad
    )
    time.sleep(PAUSA_SCROLL)
    despues = driver.execute_script("return arguments[0].scrollTop;", scrollbox)
    maximo = driver.execute_script(
        "return arguments[0].scrollHeight - arguments[0].clientHeight;", scrollbox
    )
    return antes, despues, maximo

def esperar_cambio_tabla(driver, firma_anterior=None, timeout=8):
    """
    Espera a que la tabla cambie tras seleccionar un producto.
    Evita leer datos del producto anterior y maneja los redibujados del DOM.
    """
    def firma_actual(d):
        try:
            vals = [v for v in valores_tabla(d) if v]
            
            firma = "||".join(vals[:16])
            
            if not vals:
                if firma_anterior != '__NO_DATA__' and d.find_elements(By.XPATH, "//*[normalize-space()='No data']"):
                    return '__NO_DATA__'
                return False
            if firma_anterior is None or firma != firma_anterior:
                return firma
            return False
            
        except StaleElementReferenceException:
            # Si el DOM se redibuja a mitad de la lectura, devolvemos False
            # para que WebDriverWait lo vuelva a intentar inmediatamente.
            return False

    try:
        return WebDriverWait(driver, timeout).until(firma_actual)
    except TimeoutException:
        return None

def obtener_firma_tabla(driver):
    vals = [v for v in valores_tabla(driver) if v]
    if not vals and driver.find_elements(By.XPATH, "//*[normalize-space()='No data']"):
        return '__NO_DATA__'
    return "||".join(vals[:16])

def extraer_filas_tabla(driver, producto):
    """
    Intenta leer TODAS las filas renderizadas de la tabla.
    Para la captura mostrada, el pie dice 1-4 / 4; en ese caso las 4 filas
    están renderizadas y se extraen todas.

    Si un producto llegara a tener más filas que las visibles y la tabla fuese
    virtualizada/paginada, la función desplaza internamente la tabla y deduplica.
    """
    filas = []
    vistos = set()
    sin_nuevos = 0

    # Intentar localizar un contenedor scrollable partiendo de una celda.
    celdas0 = driver.find_elements(
        By.XPATH, "//div[contains(@class,'cell')]//span[contains(@class,'cell-value')]"
    )
    scrollbox = buscar_scrollable_ancestor(driver, celdas0[0]) if celdas0 else None

    for _ in range(50):
        valores = valores_tabla(driver)

        nuevos = 0
        # El reporte tiene 4 columnas: Zona, Principio Activo, Precio, Dispo.
        for i in range(0, len(valores) - 3, 4):
            zona, principio, precio, dispo = valores[i:i+4]

            # Filtrar encabezados / vacíos.
            if not zona or zona.lower() == "zona":
                continue

            clave = (zona, principio, precio, dispo)
            if clave in vistos:
                continue

            vistos.add(clave)
            filas.append({
                "Producto": producto,
                "Zona": zona,
                "Principio Activo": principio,
                "Precio $": precio,
                "Dispo.": dispo,
            })
            nuevos += 1

        if not scrollbox:
            break

        if nuevos == 0:
            sin_nuevos += 1
        else:
            sin_nuevos = 0

        antes, despues, maximo = scroll_lista(driver, scrollbox)

        # Ya llegamos abajo o no se movió.
        if abs(despues - antes) < 1 or despues >= maximo - 2:
            # una última lectura después del scroll final
            time.sleep(0.3)
            valores = valores_tabla(driver)
            for i in range(0, len(valores) - 3, 4):
                zona, principio, precio, dispo = valores[i:i+4]
                if not zona or zona.lower() == "zona":
                    continue
                clave = (zona, principio, precio, dispo)
                if clave not in vistos:
                    vistos.add(clave)
                    filas.append({
                        "Producto": producto,
                        "Zona": zona,
                        "Principio Activo": principio,
                        "Precio $": precio,
                        "Dispo.": dispo,
                    })
            break

        if sin_nuevos >= 4:
            break

    return filas

def obtener_contador_tabla(driver):
    """
    Busca textos tipo '1 - 4 / 4' o '1-4 / 4'.
    Es solo diagnóstico; no depende de él la extracción.
    """
    texto = driver.execute_script("return document.body.innerText")
    coincidencias = re.findall(r"(\d+)\s*-\s*(\d+)\s*/\s*(\d+)", texto)
    if coincidencias:
        return tuple(map(int, coincidencias[-1]))
    return None

def extraer_catalogo():
    driver = crear_driver()
    datos_completos = []
    productos_procesados = set()
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    if os.environ.get('FARMATENCION_RESUME') != '1':
        CHECKPOINT.unlink(missing_ok=True)
    if CHECKPOINT.exists():
        with CHECKPOINT.open(encoding='utf-8') as archivo:
            for linea in archivo:
                registro = json.loads(linea)
                productos_procesados.add(registro['producto'])
                datos_completos.extend(registro['filas'])
    print(f'Reanudando: {len(productos_procesados)} productos guardados', flush=True)

    try:
        driver.get(URL)
        print("Esperando a que cargue el reporte...")
        esperar_reporte(driver)
        time.sleep(2)

        items = obtener_items_visibles(driver)
        if not items:
            raise RuntimeError("No se encontraron productos en la lista.")

        scrollbox = buscar_scrollable_ancestor(driver, items[0][1])
        if scrollbox is None:
            raise RuntimeError(
                "No pude localizar el contenedor scrollable de la lista de productos."
            )

        # Empezar desde arriba de forma determinista.
        driver.execute_script("arguments[0].scrollTop = 0;", scrollbox)
        time.sleep(0.8)

        scroll_sin_nuevos = 0

        while True:
            items = obtener_items_visibles(driver)
            nombres_visibles = [n for n, _ in items]
            nuevos_en_lote = [n for n in nombres_visibles if n not in productos_procesados]

            if nuevos_en_lote:
                scroll_sin_nuevos = 0

                # Procesar por nombre y volver a localizar el elemento antes de cada click.
                # Esto evita referencias stale cuando Looker re-renderiza el control.
                for nombre in nuevos_en_lote:
                    if nombre in productos_procesados:
                        continue

                    # Reubicar el item por texto entre los actualmente visibles.
                    candidato = None
                    for nom, el in obtener_items_visibles(driver):
                        if nom == nombre:
                            candidato = el
                            break

                    if candidato is None:
                        continue

                    print(f"-> {len(productos_procesados)+1}: {nombre}")

                    firma_previa = obtener_firma_tabla(driver)

                    # Llevarlo al centro del viewport del control y hacer click.
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center', inline:'nearest'});",
                        candidato
                    )
                    time.sleep(0.15)
                    driver.execute_script("arguments[0].click();", candidato)

                    esperar_cambio_tabla(driver, firma_previa, timeout=8)
                    time.sleep(PAUSA_SELECCION)

                    filas = extraer_filas_tabla(driver, nombre)
                    contador = obtener_contador_tabla(driver)

                    if contador:
                        ini, fin, total = contador
                        print(f"   tabla: pie {ini}-{fin}/{total}; filas capturadas={len(filas)}")
                        if len(filas) < total:
                            print(
                                f"   AVISO: el pie indica {total} filas, "
                                f"pero se capturaron {len(filas)}."
                            )
                    else:
                        print(f"   filas capturadas={len(filas)}")

                    datos_completos.extend(filas)
                    productos_procesados.add(nombre)
                    with CHECKPOINT.open('a', encoding='utf-8') as archivo:
                        archivo.write(json.dumps({'producto': nombre, 'filas': filas}, ensure_ascii=False) + '\n')

            else:
                antes, despues, maximo = scroll_lista(driver, scrollbox)
                scroll_sin_nuevos += 1

                print(
                    f"Scroll lista: {antes:.0f} -> {despues:.0f} "
                    f"(máx {maximo:.0f}); sin nuevos={scroll_sin_nuevos}"
                )

                # Fin real: estamos abajo y tras varios intentos no aparecen nombres nuevos.
                if (despues >= maximo - 2 or abs(despues - antes) < 1) and \
                   scroll_sin_nuevos >= 3:
                    print("Fin de la lista detectado.")
                    break

                if scroll_sin_nuevos >= MAX_SCROLL_SIN_NUEVOS:
                    raise RuntimeError('Demasiados scrolls sin productos nuevos; se conserva el checkpoint')

        print(f"\nProductos procesados: {len(productos_procesados)}")
        print(f"Filas totales extraídas: {len(datos_completos)}")

    finally:
        driver.quit()

    if not datos_completos:
        raise RuntimeError('El reporte no produjo filas')
    df = pd.DataFrame(datos_completos)

            # Deduplicación defensiva
    df = df.drop_duplicates(
        subset=["Producto", "Zona", "Principio Activo", "Precio $", "Dispo."]
    ).reset_index(drop=True)

    df["Precio $"] = pd.to_numeric(
        df["Precio $"].astype(str).str.replace(",", ".", regex=False),
        errors="coerce"
    )
    df["Dispo."] = pd.to_numeric(df["Dispo."], errors="coerce")

    salida = Path(__file__).resolve().parents[1] / "finales" / "catalogo_completo_farmatencion.xlsx"
    salida.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(salida, index=False)
    CHECKPOINT.unlink(missing_ok=True)
    print(f"Excel creado: {salida} | {len(df)} filas")

if __name__ == "__main__":
    extraer_catalogo()
