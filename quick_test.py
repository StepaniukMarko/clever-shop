"""
Швидкий тест сайту - перевіряє основні функції
Запуск: python quick_test.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

def quick_test():
    print("🚀 ШВИДКИЙ ТЕСТ CLEVER SHOP")
    print("=" * 50)
    print()
    
    # 1. Імпорт
    print("1️⃣  Перевірка імпортів...", end=" ")
    try:
        from app import app, db
        print("✅")
    except Exception as e:
        print(f"❌ {e}")
        return False
    
    # 2. Конфігурація
    print("2️⃣  Перевірка конфігурації...", end=" ")
    try:
        assert app.config.get('SECRET_KEY'), "SECRET_KEY не встановлено"
        print("✅")
    except Exception as e:
        print(f"❌ {e}")
        return False
    
    # 3. База даних
    print("3️⃣  Перевірка бази даних...", end=" ")
    try:
        from app import Product
        with app.app_context():
            count = Product.query.count()
            print(f"✅ (товарів: {count})")
    except Exception as e:
        print(f"❌ {e}")
        return False
    
    # 4. Routes
    print("4️⃣  Перевірка головної сторінки...", end=" ")
    try:
        with app.test_client() as client:
            response = client.get('/')
            assert response.status_code == 200, f"Статус {response.status_code}"
            print("✅")
    except Exception as e:
        print(f"❌ {e}")
        return False
    
    # 5. API
    print("5️⃣  Перевірка API...", end=" ")
    try:
        with app.test_client() as client:
            response = client.get('/api/products')
            assert response.status_code == 200, f"Статус {response.status_code}"
            print("✅")
    except Exception as e:
        print(f"❌ {e}")
        return False
    
    # 6. Відгуки (авторизація)
    print("6️⃣  Перевірка відгуків (авторизація)...", end=" ")
    try:
        import json
        with app.test_client() as client:
            response = client.post(
                '/api/products/1/reviews',
                data=json.dumps({'rating': 5}),
                content_type='application/json'
            )
            assert response.status_code == 401, f"Статус {response.status_code} (очікувався 401)"
            print("✅")
    except Exception as e:
        print(f"❌ {e}")
        return False
    
    # 7. Templates
    print("7️⃣  Перевірка templates...", end=" ")
    try:
        templates = ['base.html', 'index.html', 'product.html']
        for t in templates:
            assert os.path.exists(f'templates/{t}'), f"{t} не знайдено"
        print("✅")
    except Exception as e:
        print(f"❌ {e}")
        return False
    
    # 8. Static files
    print("8️⃣  Перевірка статичних файлів...", end=" ")
    try:
        files = ['static/style.css', 'static/script.js']
        for f in files:
            assert os.path.exists(f), f"{f} не знайдено"
        print("✅")
    except Exception as e:
        print(f"❌ {e}")
        return False
    
    print()
    print("=" * 50)
    print("🎉 ВСІ ШВИДКІ ТЕСТИ ПРОЙДЕНО!")
    print("=" * 50)
    print()
    print("💡 Для повного тестування запусти: python test_app.py")
    print()
    
    return True

if __name__ == '__main__':
    success = quick_test()
    sys.exit(0 if success else 1)
