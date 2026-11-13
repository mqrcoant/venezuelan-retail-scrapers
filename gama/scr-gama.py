import csv
import time
import requests

# URL base de la API de búsqueda y dominio de imágenes de Gama en Línea
BASE_URL = "https://api.cl94ncbhsi-excelsior1-p1-public.model-t.cc.commerce.ondemand.com/occ/v2/egb2c-spa/products/search"
MEDIA_DOMAIN = "https://egb2c.cl94ncbhsi-excelsior1-p1-public.model-t.cc.commerce.ondemand.com"

def obtener_productos_por_categoria(category_code, warehouse="S007", page_size=100):
    all_products = []
    current_page = 0
    total_pages = 1  # Se actualizará con la primera respuesta

    fields_param = (
        "products(dvMessage,score,baseProduct,taxWithDiscount(formattedValue,value),"
        "seoName,code,name,summary,configurable,configuratorType,multidimensional,"
        "price(FULL),images(FULL),stock(FULL),averageRating,variantOptions,"
        "vatAmountPrice(formattedValue),totalWithVatPrice(formattedValue,value),"
        "totalPriceWithNoDiscount(formattedValue),basePriceWithDiscount(formattedValue),"
        "categories(code,name),promotions(code,name,message,promotionType,labelColor,"
        "labelTextColor,dvMessage)),facets,breadcrumbs,pagination(DEFAULT),sorts(DEFAULT),"
        "freeTextSearch,currentQuery"
    )

    while current_page < total_pages:
        query_str = f":relevance:allCategories:{category_code}"
        url = f"{BASE_URL}?fields={fields_param}&query={query_str}&pageSize={page_size}&currentPage={current_page}&lang=es&curr=REF&warehouse={warehouse}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        try:
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                print(f"Error {response.status_code} al consultar la categoría {category_code}")
                break

            data = response.json()

            # Obtener productos de la página actual
            products = data.get("products", [])
            all_products.extend(products)

            # Gestionar paginación
            pagination = data.get("pagination", {})
            total_pages = pagination.get("totalPages", 1)
            current_page += 1

            # Pequeña pausa para no saturar el servidor y evitar bloqueos
            time.sleep(0.5)

        except Exception as e:
            print(f"Excepción en categoría {category_code}: {e}")
            break

    return all_products

def procesar_catalogo():
    # Lista de categorías principales
    lista_categorias = [
        "A01", # Despensa
        "A02", # Alimentos frescos
        "A03", # Congelados y refrigerados
        "A04", # Licores
        "A05", # Bebidas
        "A06", # Cuidado personal y salud
        "A07", # Limpieza
        "A08", # Mascotas
        "A09", # Hogar
    ]

    productos_procesados = []
    sku_vistos = set()  # Set para evitar duplicados

    for cat_code in lista_categorias:
        print(f"Extrayendo categoría código: {cat_code}...")
        productos = obtener_productos_por_categoria(cat_code)

        for p in productos:
            sku = p.get("code")
            
            # Evitar productos duplicados en el CSV
            if sku in sku_vistos:
                continue
            sku_vistos.add(sku)

            nombre = p.get("name")

            # --- LÓGICA DE CATEGORÍAS ---
            cats = p.get("categories", [])
            nombres_cats = [c.get("name", "") for c in cats if c.get("name")]
            
            if nombres_cats:
                categoria_principal = nombres_cats[0]
                subcategorias = " > ".join(nombres_cats[1:]) if len(nombres_cats) > 1 else "N/A"
            else:
                categoria_principal = "N/A"
                subcategorias = "N/A"

            # --- LÓGICA DE IMAGEN ---
            imagenes = p.get("images", [])
            url_imagen = "N/A"
            if imagenes:
                # Buscamos preferiblemente la imagen formato 'product' (300x300)
                img_obj = next((img for img in imagenes if img.get("format") == "product"), None)
                if not img_obj:
                    img_obj = imagenes[0] # Si no existe, tomamos la primera disponible
                
                rel_url = img_obj.get("url", "")
                if rel_url:
                    url_imagen = f"{MEDIA_DOMAIN}{rel_url}"

            # --- PRECIOS E IMPUESTOS ---
            precio_base = p.get("basePriceWithDiscount", {}).get("formattedValue", "N/A")
            iva_ref = p.get("taxWithDiscount", {}).get("formattedValue", "N/A")
            precio_final = p.get("totalWithVatPrice", {}).get("formattedValue") or p.get("price", {}).get("formattedValue", "N/A")

            productos_procesados.append({
                "SKU_Interno": sku,
                "Nombre": nombre,
                "Categoria_Principal": categoria_principal,
                "Subcategorias": subcategorias,
                "Precio_Base": precio_base,
                "IVA_Ref": iva_ref,
                "Precio_Final": precio_final,
                "Imagen_URL": url_imagen
            })

    # Guardar en CSV
    nombre_archivo = "catalogo_gama_con_imagenes.csv"
    with open(nombre_archivo, mode="w", newline="", encoding="utf-8-sig") as archivo_csv:
        fieldnames = [
            "SKU_Interno", "Nombre", "Categoria_Principal", 
            "Subcategorias", "Precio_Base", "IVA_Ref", 
            "Precio_Final", "Imagen_URL"
        ]
        writer = csv.DictWriter(archivo_csv, fieldnames=fieldnames)
        
        writer.writeheader()
        for prod in productos_procesados:
            writer.writerow(prod)

    print(f"\n¡Proceso completado! Se guardaron {len(productos_procesados)} productos únicos en '{nombre_archivo}'.")

if __name__ == "__main__":
    procesar_catalogo()