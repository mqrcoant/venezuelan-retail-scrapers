# Scrapers de Kuantip

Este repositorio tiene como raíz la antigua carpeta `scripts`. El commit `72e8c2b` conserva la versión primitiva de los scripts y datos de scraping, con tokens privados sustituidos por variables de entorno. El respaldo local íntegro anterior a cualquier cambio está en `../sandbox/respaldo-scripts-primitivo.zip` y no se publica.

## Estructura

- `pipeline.py`: ejecuta una tienda o todas, comprueba que cada salida sea de la corrida nueva y convierte CSV finales a XLSX sin transformar EAN/SKU en números.
- `finales/`: resultados nuevos listos para revisar. Las tiendas con múltiples archivos usan una subcarpeta (`kalea`, `dataprecio`, `emporium`, `farmago`, `locatel`, `saas`, `farma-actual`, `tucentralonline`).
- Carpeta de cada tienda: scraper, pruebas históricas y archivos de trabajo. Los archivos antiguos que siguen allí no representan necesariamente una corrida actual.
- `logs/`: un log por script y resumen JSON por corrida; no se publica.
- `backoffice/` y `experimento-iva/`: trabajos exteriores a tiendas, organizados y excluidos de las corridas.
- `tantovital/NO_USAR.md`: precios no confiables; se omite por decisión expresa del usuario.

## Ejecutar

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
python pipeline.py --list
$env:BCV_RATE = '904.45'  # indicar la tasa correspondiente a la fecha de la corrida
$env:PLAZA_EMAIL = '<usuario>'
$env:PLAZA_PASSWORD = '<contraseña>'
python pipeline.py --store kalea
python pipeline.py --all --timeout 1800
```

No escribas credenciales en scripts ni en archivos rastreados por Git. `BCV_RATE` es necesaria para Farmago, Locatel y Farma Actual. Plaza necesita sus dos variables. El pipeline informa `pendiente` si faltan.

Dataprecio ejecuta en orden el scraper inicial, los dos rescates y el separador. Fusiona por `ID_Dataprecio` y `Tienda` y exige las 17 tiendas antes de publicar los Excel. Si el sitio no muestra productos reales o la paginación verificable, no se publica un resultado incompleto.

Los scripts con navegación pesada pueden requerir un `--timeout` mayor. Un código de salida cero sin archivos nuevos se considera error. El resumen y los logs muestran la causa; no se reutilizan archivos antiguos como éxitos.

SaaS, Emporium, Superfreshmarket, TuCentral y Farmatención guardan puntos de reanudación locales en `logs/`. Tras una interrupción, usa `python pipeline.py --store saas --resume --timeout 14400` (sustituye `saas` por la tienda correspondiente). No copies un CSV histórico como si fuera una corrida nueva. TuCentral produce un consolidado y un detalle de precio y stock por sede.

Farma Actual muestra precios al público, pero en el HTML consultado no informa el IVA de cada producto. Su archivo `maestro_tu_farmacia_actual_base.xlsx` deja vacía la base cuando `estado_iva=no_informado`; solo calcula base si una fuente futura aporta `iva_pct` explícito (0 o 16). La tasa usada en la corrida del 12/11/2026 fue 904,45 Bs/USD.

En SaaS, el campo público VTEX `Price` coincide con el precio mostrado en la ficha; `Tax` no debe sumarse otra vez. `precio_con_iva` usa `Price` y `precio_base` queda vacío mientras no se verifique el tratamiento fiscal por producto. Los checkpoints antiguos se corrigen al generar el CSV final.

Superfresh conserva los 4.228 precios finales publicados, pero deja `precio_base_ref` vacío y marca `estado_iva=no_informado` porque la regla por categoría del script anterior no acreditaba el IVA de cada artículo.

TuCentral usa Playwright visible y pausas aleatorias de 3,5 a 7,5 segundos por página, como el flujo original. Una prueba de tres páginas con esa configuración devolvió 200 y todos los productos; el checkpoint permite reanudar una corrida larga si vuelve a aparecer 403/503. El pipeline exige datos de las 18 sedes antes de generar sus dos Excel.

Emporium guarda el catálogo completo y un archivo `revisar_emporium.xlsx` con códigos de barras de formato dudoso o precios no positivos. SaaS separa productos con precio, sin precio y sin EAN/SKU; ninguna de estas tres salidas suma `Tax` al precio mostrado.

Farmatención usa ahora `scraper-farmatencion-playwright.py`; el antiguo Selenium queda como referencia. En la revisión del 14/11/2026, la lista pública mostró 5.001 nombres y la tabla sin filtrar 27.664 filas. Para exigir una cobertura comparable en esa corrida, define `FARMATENCION_MIN_PRODUCTS=5000` y `FARMATENCION_MIN_ROWS=27000` antes de usar `--store farmatencion --resume`.
