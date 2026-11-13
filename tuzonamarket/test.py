import requests
import json

def diagnostico_coca_cola():
    url = "https://api.tuzonamarket.com/api/categoria/supermercado/2/bebidas?pag=1"
    print(f"Consultando API: {url}...\n")
    
    respuesta = requests.get(url)
    if respuesta.status_code != 200:
        print(f"Error HTTP: {respuesta.status_code}")
        return
        
    datos = respuesta.json()
    productos = datos.get('producto', {}).get('data', [])
    
    for item in productos:
        if 'coca' in item.get('nombre', '').lower():
            print("¡Coca Cola encontrada! Aquí está su estructura JSON exacta:\n")
            print(json.dumps(item, indent=4, ensure_ascii=False))
            break

if __name__ == "__main__":
    diagnostico_coca_cola()