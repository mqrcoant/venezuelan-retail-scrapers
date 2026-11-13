# Scrapers de Kuantip

Este repositorio tiene como raíz la antigua carpeta `scripts`. El commit `72e8c2b` conserva la versión primitiva de los scripts y datos de scraping, con tokens privados sustituidos por variables de entorno. El respaldo local íntegro anterior a cualquier cambio está en `../sandbox/respaldo-scripts-primitivo.zip` y no se publica.

## Estructura

- `pipeline.py`: ejecuta una tienda o todas, comprueba que cada salida sea de la corrida nueva y convierte CSV finales a XLSX sin transformar EAN/SKU en números.
- `finales/`: resultados nuevos listos para revisar. Las tiendas con múltiples archivos usan una subcarpeta (`kalea`, `dataprecio`, `farmago`, `locatel`, `saas`, `farma-actual`).
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
