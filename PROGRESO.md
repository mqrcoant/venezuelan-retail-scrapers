# Estado breve (13/11/2026)

- Repositorio público: https://github.com/mqrcoant/kuantip-scrapers. Base primitiva sanitizada: `72e8c2b`; respaldo íntegro local: `../sandbox/respaldo-scripts-primitivo.zip`.
- Pipeline: `pipeline.py`; Excel nuevos en `finales/`; logs locales en `logs/`. Tantovital excluida. Backoffice e IVA organizados, sin ejecutar.
- Completados: Kalea (maestro + 6), Celicor, Gama, MiBodega, Río Market, Farma Actual (tasa 904,45), Locatel, Madison (3.927 variantes; sin EAN expuestos).
- Bloqueos: Badan/BodegaBE/Plaza/Licores 403; Farmago 522; Dataprecio API 403 y tarjetas vacías; Farmatención no carga reporte; Emporium terminó parcial por límite de tiempo.
- En curso al escribir: `pipeline.py --all` (desde 12/11 23:44, ahora en Superfreshmarket), SaaS reintento (sesión 43977). Revisar `logs/*_resumen.json` y `logs/*` antes de repetir.
- Pendiente: terminar corridas, revisar fallos y archivos nuevos, preparar commit de cambios y subirlo. Cambios de código y Excel ya están staged; CSV de trabajo no. Evaluación Scrapling en `SCRAPLING_EVALUACION.md`.
