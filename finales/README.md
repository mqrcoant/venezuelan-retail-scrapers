# Catálogos de nuevas corridas

Todos los `.xlsx` de esta carpeta son resultados creados **después** de la versión primitiva del repositorio. Los archivos anteriores se recuperan exactamente desde el [commit `72e8c2b`](https://github.com/mqrcoant/kuantip-scrapers/tree/72e8c2b); también existe un respaldo local íntegro en `../../sandbox/respaldo-scripts-primitivo.zip`. Los CSV dentro de carpetas de tiendas son archivos de trabajo y pueden haber sido reemplazados por una corrida nueva: para comparar con el pasado, usa ese commit.

| Tienda | Excel nuevos | Filas | Observación |
|---|---|---:|---|
| Kalea | `kalea/kalea_catalogo_completo.xlsx` y seis archivos por sede/tipo | 36.328 en el maestro | Separados por Caracas/Carabobo, estándar/ecommerce/faltantes. |
| Celicor | `celicor_la_castellana.xlsx` | 2.361 | Corrida nueva. |
| Gama | `catalogo_gama_con_imagenes.xlsx` | 3.081 | Corrida nueva. |
| MiBodega | `mibodega_maestro_total.xlsx` | 1.511 | Corrida nueva. |
| Río Market | `riomarket_maestro_total.xlsx` | 4.500 | Corrida nueva. |
| Farma Actual | `farma-actual/maestro_tu_farmacia_actual.xlsx` y `maestro_tu_farmacia_actual_base.xlsx` | 3.644 bruto; 3.642 depurados | La base queda vacía cuando el IVA individual no está informado; tasa BCV 904,45. |
| Locatel | `locatel/prods_locatel.xlsx` | 11.130 | Corrida nueva. |
| Madison | `maestro_madison.xlsx` | 3.927 | Incluye todas las variantes expuestas; la fuente no entregó EAN. |
| Tuzona Market | `productos_tuzonamarket_completo.xlsx` | 11.533 | Corrida nueva. |
| Viva | `catalogo_viva.xlsx` | 1.974 | Corrida nueva. |
| Superfresh | `maestro_super_fresh_market.xlsx` | 4.228 | Precio base vacío por IVA no informado. |
| SaaS | `saas/prods_saas.xlsx`, `saas/saas-sin-precio.xlsx`, `saas/saas-faltantes.xlsx` | 11.104; 13.027; 1.058 | Precio visible VTEX `Price`; no se suma `Tax`. |
| Emporium | `emporium/catalogo_emporium.xlsx` y `revisar_emporium.xlsx` | 3.672; 50 para revisión | El segundo archivo reúne 45 EAN dudosos y 5 precios no positivos. |

**Farmatención:** el Excel situado en `../farmatencion/catalogo_completo_farmatencion.xlsx` es **histórico**, con 3.274 productos distintos y 25.985 filas. La nueva corrida sigue en curso y solo se escribirá aquí al completarse. **TuCentral:** la nueva corrida de 18 sedes también está en curso; su versión final irá a `tucentralonline/`.
