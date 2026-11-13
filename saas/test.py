import requests
import json

slug = "112319-fanta-naranja-2lt"
# Usamos el parámetro linkText para apuntar al producto exacto
url = f"https://www.farmaciasaas.com/api/catalog_system/pub/products/search/?linkText={slug}"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

respuesta = requests.get(url, headers=headers)

if respuesta.status_code in [200, 206]:
    datos = respuesta.json()
    
    if datos:
        producto = datos[0] 
        oferta = producto['items'][0]['sellers'][0]['commertialOffer']
        
        precio_base = oferta.get('Price', 0)
        impuesto = oferta.get('Tax', 0)
        precio_final = round(precio_base + impuesto, 2)
        
        print(f"--- AUDITORÍA DE PRODUCTO EXACTO ---")
        print(f"Nombre: {producto['productName']}")
        print(f"Precio Base (sin IVA): {precio_base}")
        print(f"Impuesto (IVA VTEX): {impuesto}")
        print(f"Precio FINAL: {precio_final}")
        
    else:
        print("El servidor no devolvió datos. El slug no coincide.")
else:
    print(f"Error HTTP: {respuesta.status_code}")