import requests
import json

def test_madison_producto():
    url_bruta = input("Pega la URL completa de Madison: ").strip()
    
    # Limpiamos la URL quitando cualquier parámetro basura que venga después del signo de interrogación
    url_limpia = url_bruta.split('?')[0]
    url_json = f"{url_limpia}.json"
    
    # Cabeceras robustas para evadir bloqueos básicos de Cloudflare
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }
    
    print(f"\nConsultando API nativa: {url_json}...")
    
    try:
        # El timeout obliga al script a detenerse si el servidor no responde en 10 segundos
        respuesta = requests.get(url_json, headers=headers, timeout=10)
        
        if respuesta.status_code == 200:
            datos = respuesta.json()
            producto = datos.get('product', {})
            variante = producto['variants'][0]
            
            precio_base = float(variante.get('price', 0))
            paga_impuesto = variante.get('taxable', False)
            
            if paga_impuesto:
                precio_final = round(precio_base * 1.16, 2)
                estado_iva = "SÍ (Suma 16%)"
            else:
                precio_final = round(precio_base, 2)
                estado_iva = "NO (Exento 0%)"
                
            print("\n--- RESULTADOS DE LA EXTRACCIÓN ---")
            print(f"Nombre: {producto.get('title')}")
            print(f"Precio Base (API): ${precio_base}")
            print(f"¿Paga Impuesto? (taxable): {estado_iva}")
            print(f"Precio FINAL Calculado: ${precio_final}")
            
        else:
            print(f"Error HTTP: {respuesta.status_code}. El firewall de Madison bloqueó la petición o la URL es inválida.")
            
    except requests.exceptions.Timeout:
        print("\nError: Tiempo de espera agotado (Timeout). El firewall de Madison está bloqueando silenciosamente a Python.")
    except Exception as e:
        print(f"\nError de conexión: {e}")

if __name__ == "__main__":
    test_madison_producto()