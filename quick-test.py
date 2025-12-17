# Tests rápidos para verificar que todo funciona
# Uso: python quick-test.py [local|prod]

import sys
import requests
import json

def test_local():
    """Tests para ambiente local"""
    print("🧪 Testing ambiente LOCAL...\n")
    
    base_url = "http://localhost"
    
    tests = [
        {
            "name": "Backoffice Health",
            "url": f"{base_url}:8080/admin",
            "method": "GET",
            "expected_status": 200
        },
        {
            "name": "Checkout UI",
            "url": f"{base_url}:8001/index.html",
            "method": "GET",
            "expected_status": 200
        },
        {
            "name": "WhatsApp Server Health",
            "url": f"{base_url}:9002/",
            "method": "GET",
            "expected_status": 200
        },
        {
            "name": "Backoffice API - Users",
            "url": f"{base_url}:8080/users",
            "method": "GET",
            "headers": {"x-api-key": "19PxrNUo0i6XWVgc_GSeRljrtL5lCrj0gi6Ir9rftBk"},
            "expected_status": 200
        },
        {
            "name": "Backoffice API - Products",
            "url": f"{base_url}:8080/products",
            "method": "GET",
            "headers": {"x-api-key": "19PxrNUo0i6XWVgc_GSeRljrtL5lCrj0gi6Ir9rftBk"},
            "expected_status": 200
        }
    ]
    
    run_tests(tests)

def test_prod():
    """Tests para ambiente de producción"""
    print("🧪 Testing ambiente PRODUCCIÓN...\n")
    
    base_url = "https://yoplabs-agent-demo-697941530409.us-central1.run.app"
    
    tests = [
        {
            "name": "Health Check",
            "url": f"{base_url}/healthz",
            "method": "GET",
            "expected_status": 200
        },
        {
            "name": "Checkout UI",
            "url": f"{base_url}/checkout-ui/index.html",
            "method": "GET",
            "expected_status": 200
        },
        {
            "name": "WhatsApp Endpoint (debe devolver 405 sin POST)",
            "url": f"{base_url}/whatsapp",
            "method": "GET",
            "expected_status": 405  # Method not allowed para GET
        },
        {
            "name": "Backoffice API - Users",
            "url": f"{base_url}/users",
            "method": "GET",
            "headers": {"x-api-key": "19PxrNUo0i6XWVgc_GSeRljrtL5lCrj0gi6Ir9rftBk"},
            "expected_status": 200
        },
        {
            "name": "Backoffice API - Products",
            "url": f"{base_url}/products",
            "method": "GET",
            "headers": {"x-api-key": "19PxrNUo0i6XWVgc_GSeRljrtL5lCrj0gi6Ir9rftBk"},
            "expected_status": 200
        }
    ]
    
    run_tests(tests)

def run_tests(tests):
    """Ejecuta una lista de tests"""
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            print(f"Testing: {test['name']}...")
            
            method = test.get('method', 'GET')
            headers = test.get('headers', {})
            data = test.get('data')
            
            if method == 'GET':
                response = requests.get(test['url'], headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(test['url'], headers=headers, json=data, timeout=10)
            
            expected = test.get('expected_status', 200)
            
            if response.status_code == expected:
                print(f"  ✅ PASS - Status: {response.status_code}")
                passed += 1
                
                # Si es una respuesta JSON, mostrar resumen
                if 'application/json' in response.headers.get('content-type', ''):
                    try:
                        data = response.json()
                        if isinstance(data, list):
                            print(f"     📊 Items: {len(data)}")
                        elif isinstance(data, dict):
                            print(f"     📊 Keys: {list(data.keys())[:3]}")
                    except:
                        pass
            else:
                print(f"  ❌ FAIL - Expected {expected}, got {response.status_code}")
                print(f"     Response: {response.text[:200]}")
                failed += 1
                
        except requests.exceptions.Timeout:
            print(f"  ❌ FAIL - Timeout")
            failed += 1
        except requests.exceptions.ConnectionError:
            print(f"  ❌ FAIL - Connection error (¿Servicio corriendo?)")
            failed += 1
        except Exception as e:
            print(f"  ❌ FAIL - {str(e)}")
            failed += 1
        
        print()
    
    # Resumen
    total = passed + failed
    print("=" * 50)
    print(f"📊 Resumen: {passed}/{total} tests pasaron")
    if failed > 0:
        print(f"⚠️  {failed} tests fallaron")
        return False
    else:
        print("✅ Todos los tests pasaron!")
        return True

def main():
    if len(sys.argv) < 2:
        print("❌ Uso: python quick-test.py [local|prod]")
        print("\nEjemplos:")
        print("  python quick-test.py local   - Test ambiente local")
        print("  python quick-test.py prod    - Test ambiente producción")
        sys.exit(1)
    
    mode = sys.argv[1].lower()
    
    if mode == "local":
        success = test_local()
    elif mode == "prod":
        success = test_prod()
    else:
        print(f"❌ Modo inválido: {mode}")
        print("   Usar 'local' o 'prod'")
        sys.exit(1)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
