import requests
import json

def test_precios_locatel():
    # Buscamos el producto específico de tu captura
    url = "https://www.locatel.com.ve/api/catalog_system/pub/products/search/alive?_from=0&_to=3"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    print(f"Consultando API: {url}\n")
    respuesta = requests.get(url, headers=headers)
    
    if respuesta.status_code not in [200, 206]:
        print(f"Error HTTP: {respuesta.status_code}")
        return
        
    datos = respuesta.json()
    if not datos:
        print("No se encontraron productos.")
        return
        
    for prod in datos:
        nombre = prod.get('productName')
        print(f"Producto: {nombre}")
        print("-" * 50)
        
        # 1. Buscar en las especificaciones personalizadas
        print("** Especificaciones (allSpecifications) **")
        for spec in prod.get('allSpecifications', []):
            if 'precio' in spec.lower() or 'ref' in spec.lower() or 'usd' in spec.lower():
                print(f"  [!] {spec}: {prod.get(spec)}")
            
        for item in prod.get('items', [])[:1]:
            for vendedor in item.get('sellers', [])[:1]:
                oferta = vendedor.get('commertialOffer', {})
                
                p_base = oferta.get('Price', 0)
                impuesto = oferta.get('Tax', 0)
                p_final = round(p_base + impuesto, 2)
                
                # 2. Desglose de los precios que ya identificamos
                print("\n** Datos Financieros (commertialOffer) **")
                print(f"  Price (Base): {p_base}")
                print(f"  Tax (IVA):    {impuesto}")
                print(f"  -> Total Calculado (Base + IVA): {p_final}")
                
                # 3. Explorar el resto de variables numéricas buscando el 6.60
                print("\n** Otras variables numéricas en la oferta **")
                for k, v in oferta.items():
                    if isinstance(v, (int, float)) and k not in ['Price', 'Tax']:
                        print(f"  {k}: {v}")
        print("=" * 60 + "\n")

if __name__ == "__main__":
    test_precios_locatel()