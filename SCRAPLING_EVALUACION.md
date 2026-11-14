# Evaluación de Scrapling para estos scrapers

Fuente: [repositorio oficial](https://github.com/D4Vinci/Scrapling) y [documentación oficial](https://scrapling.readthedocs.io/en/latest/).

## Resultado de la prueba local

Se instaló Scrapling 0.5.1 en un entorno aislado, fuera de este repositorio. En la prueba limitada autorizada, `StealthyFetcher` no obtuvo productos de Badan: el sitio siguió respondiendo 403. En Dataprecio no logró obtener tarjetas reales tras la protección de Cloudflare. Por eso no se sustituyó ningún scraper existente por Scrapling ni se publicaron datos de esas pruebas.

## Oportunidades concretas

1. **Madison Center (prioridad alta).** El scraper primitivo procesaba solo la primera variante disponible. Se mejoró su consulta JSON existente para incluir todas las variantes, disponibilidad, descripción y precio anterior: 3.927 filas nuevas frente a 3.383 anteriores. [`ShopifySpider`](https://scrapling.readthedocs.io/en/latest/spiders/platform-templates.html) ofrece ese recorrido, deduplicación y control de ritmo como alternativa para una migración futura. En esta corrida Shopify no publicó ningún EAN, así que Scrapling tampoco podría completarlos desde ese endpoint.
2. **Dataprecio (solo diagnóstico, de momento).** La [captura de respuestas de red](https://scrapling.readthedocs.io/en/latest/fetching/stealthy.html#network-history) permitiría ver la API y la paginación real detrás de la interfaz. En la corrida actual, `/api/search/sample-products` y otras llamadas devolvieron 403; la captura no aporta catálogo mientras ese acceso falle. El selector adaptativo tampoco arregla un 403 de API.
3. **Scrapers de HTML con cambios de diseño.** La [selección adaptativa](https://scrapling.readthedocs.io/en/latest/parsing/adaptive.html) podría ayudar a relocalizar tarjetas o campos cuando cambian clases CSS. Debe validarse con ejemplos guardados y controles de cantidad para no asociar un precio con otro producto.
4. **Corridas extensas.** Los [spiders](https://scrapling.readthedocs.io/en/latest/) ofrecen AutoThrottle, reintentos y pausa/reanudación con `crawldir`. Son candidatos para Locatel, Dataprecio y Emporium, donde una ejecución monolítica larga pierde progreso al interrumpirse. Requieren adaptar cada fuente y validar el resultado contra el scraper actual.
5. **SaaS: más datos sin cambiar de librería.** La API VTEX pública usada por el scraper también entrega `ListPrice`, `AvailableQuantity`, `IsAvailable`, `PriceValidUntil`, identificadores por ítem y posibles variantes. El script actual conserva un EAN y la primera oferta con precio por producto. Se puede crear una salida por variante y vendedor con esos campos, validando primero precios y duplicados. Scrapling no es necesario para leer este JSON; su aporte sería la gestión de reintentos y reanudación.

## Límites

Scrapling no genera EAN/GTIN, precio base o inventario que la tienda no exponga. Los productos detrás de sesión, bloqueo o API inaccesible necesitan una fuente de datos autorizada y verificable. En Kalea ya se consulta directamente el catálogo JSON de Supabase, por lo que cambiarlo a un navegador Scrapling añadiría complejidad sin demostrar más campos.
