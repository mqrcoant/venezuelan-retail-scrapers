"""Extrae el reporte público de Farmatención con checkpoint por producto."""

import json
import os
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright


URL = 'https://datastudio.google.com/reporting/f7732857-56bb-4557-8433-6cee0b5cd775/page/V2xOF'
ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / 'logs' / 'farmatencion_checkpoint.jsonl'
OUTPUT = ROOT / 'finales' / 'catalogo_completo_farmatencion.xlsx'


def leer_checkpoint():
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    if os.environ.get('FARMATENCION_RESUME') != '1':
        CHECKPOINT.unlink(missing_ok=True)
    registros = {}
    if CHECKPOINT.exists():
        with CHECKPOINT.open(encoding='utf-8') as archivo:
            for linea in archivo:
                dato = json.loads(linea)
                registros[dato['producto']] = dato['filas']
    return registros


def guardar_producto(nombre, filas):
    with CHECKPOINT.open('a', encoding='utf-8') as archivo:
        archivo.write(json.dumps({'producto': nombre, 'filas': filas}, ensure_ascii=False) + '\n')


def celdas_y_total(page):
    return page.evaluate(r"""() => {
        const valores = [...document.querySelectorAll('div.cell span.cell-value')]
            .map(el => (el.textContent || '').trim());
        const matches = [...document.body.innerText.matchAll(/(\d+)\s*-\s*(\d+)\s*\/\s*(\d+)/g)];
        const total = matches.length ? Number(matches[matches.length - 1][3]) : null;
        return {valores, total};
    }""")


def filas_producto(page, nombre, firma_previa):
    page.wait_for_timeout(900)
    actual = celdas_y_total(page)
    firma = tuple(actual['valores'][:16])
    if firma == firma_previa:
        page.wait_for_timeout(1200)
        actual = celdas_y_total(page)
    valores = actual['valores']
    total = actual['total']
    if total is None:
        raise RuntimeError(f'No aparece el contador de tabla para {nombre}')
    if len(valores) % 4:
        raise RuntimeError(f'La tabla de {nombre} tiene {len(valores)} celdas, no múltiplo de 4')
    filas = []
    for indice in range(0, len(valores), 4):
        zona, principio, precio, dispo = valores[indice:indice + 4]
        if zona and zona.lower() != 'zona':
            filas.append({'Producto': nombre, 'Zona': zona,
                          'Principio Activo': principio, 'Precio $': precio,
                          'Dispo.': dispo})
    if len(filas) != total:
        raise RuntimeError(f'{nombre}: pie indica {total} filas y se leyeron {len(filas)}')
    return filas


def main():
    procesados = leer_checkpoint()
    print(f'Reanudando {len(procesados)} productos', flush=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={'width': 1280, 'height': 900})
            page.goto(URL, wait_until='domcontentloaded', timeout=60000)
            page.locator('div.item-single').first.wait_for(timeout=60000)
            scrollbox = page.locator('div.item-single').first.evaluate_handle("""el => {
                while (el) {
                    const style = getComputedStyle(el);
                    if (['auto', 'scroll'].includes(style.overflowY) &&
                        el.scrollHeight > el.clientHeight + 5) return el;
                    el = el.parentElement;
                }
                return null;
            }""")
            if scrollbox.evaluate('el => el === null'):
                raise RuntimeError('No se encontró la lista desplazable')
            scrollbox.evaluate('el => el.scrollTop = 0')
            sin_nuevos = 0
            while True:
                nombres = [nombre.strip() for nombre in page.locator('div.item-single span.dimension-value').all_text_contents()]
                nuevos = 0
                for indice, nombre in enumerate(nombres):
                    if not nombre or nombre in procesados:
                        continue
                    firma_previa = tuple(celdas_y_total(page)['valores'][:16])
                    page.locator('div.item-single').nth(indice).click()
                    filas = filas_producto(page, nombre, firma_previa)
                    guardar_producto(nombre, filas)
                    procesados[nombre] = filas
                    nuevos += 1
                    print(f'{len(procesados)}: {nombre} | {len(filas)} filas', flush=True)
                sin_nuevos = 0 if nuevos else sin_nuevos + 1
                antes, despues, maximo = scrollbox.evaluate("""el => {
                    const antes = el.scrollTop;
                    el.scrollTop = Math.min(el.scrollTop + el.clientHeight * .72, el.scrollHeight);
                    return [antes, el.scrollTop, el.scrollHeight - el.clientHeight];
                }""")
                page.wait_for_timeout(150)
                if despues >= maximo - 2 and sin_nuevos >= 3:
                    break
                if abs(despues - antes) < 1 and despues < maximo - 2:
                    raise RuntimeError('El scroll del reporte se detuvo inesperadamente')
        finally:
            browser.close()

    min_productos = int(os.environ.get('FARMATENCION_MIN_PRODUCTS', '0'))
    if len(procesados) < min_productos:
        raise RuntimeError(f'Solo {len(procesados)} de al menos {min_productos} productos')
    datos = [fila for filas in procesados.values() for fila in filas]
    if not datos:
        raise RuntimeError('No se obtuvieron filas')
    frame = pd.DataFrame(datos).drop_duplicates()
    frame['Precio $'] = pd.to_numeric(frame['Precio $'].astype(str).str.replace(',', '.', regex=False), errors='coerce')
    frame['Dispo.'] = pd.to_numeric(frame['Dispo.'], errors='coerce')
    min_filas = int(os.environ.get('FARMATENCION_MIN_ROWS', '0'))
    if len(frame) < min_filas:
        raise RuntimeError(f'Solo {len(frame)} de al menos {min_filas} filas')
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporal = OUTPUT.with_name(OUTPUT.stem + '.tmp.xlsx')
    frame.to_excel(temporal, index=False)
    temporal.replace(OUTPUT)
    CHECKPOINT.unlink(missing_ok=True)
    print(f'Final: {len(procesados)} productos, {len(frame)} filas en {OUTPUT}', flush=True)


if __name__ == '__main__':
    main()
