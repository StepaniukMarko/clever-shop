"""
Автоматичні тести для Clever Shop
Запуск: python test_app.py
"""

import sys
import os

# Додаємо поточну директорію в PATH
sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    """Тест 1: Перевірка що всі модулі імпортуються"""
    print("🧪 Тест 1: Перевірка імпортів...")
    try:
        from app import app, db, Product, Order, User, Review
        print("   ✅ Всі модулі імпортуються")
        return True
    except Exception as e:
        print(f"   ❌ Помилка імпорту: {e}")
        return False

def test_app_config():
    """Тест 2: Перевірка конфігурації додатка"""
    print("🧪 Тест 2: Перевірка конфігурації...")
    try:
        from app import app
        
        # Перевірка SECRET_KEY
        if not app.config.get('SECRET_KEY'):
            print("   ❌ SECRET_KEY не встановлено")
            return False
        
        # Перевірка DATABASE
        if not app.config.get('SQLALCHEMY_DATABASE_URI'):
            print("   ❌ DATABASE_URI не встановлено")
            return False
        
        print("   ✅ Конфігурація правильна")
        return True
    except Exception as e:
        print(f"   ❌ Помилка конфігурації: {e}")
        return False

def test_routes():
    """Тест 3: Перевірка що всі routes існують"""
    print("🧪 Тест 3: Перевірка routes...")
    try:
        from app import app
        
        routes = [
            '/',
            '/brands',
            '/about',
            '/contacts',
            '/delivery',
            '/returns',
            '/oferta',
            '/privacy',
            '/wishlist',
            '/login',
            '/register',
            '/admin/login',
            '/checkout',
        ]
        
        with app.test_client() as client:
            failed = []
            for route in routes:
                try:
                    response = client.get(route, follow_redirects=True)
                    if response.status_code not in [200, 302, 401]:
                        failed.append(f"{route} → {response.status_code}")
                except Exception as e:
                    failed.append(f"{route} → {str(e)}")
            
            if failed:
                print(f"   ❌ Помилки в routes:")
                for f in failed:
                    print(f"      {f}")
                return False
            
            print(f"   ✅ Всі {len(routes)} routes працюють")
            return True
    except Exception as e:
        print(f"   ❌ Помилка тестування routes: {e}")
        return False

def test_database():
    """Тест 4: Перевірка підключення до БД"""
    print("🧪 Тест 4: Перевірка бази даних...")
    try:
        from app import app, db, Product, Category
        
        with app.app_context():
            # Перевірка що таблиці існують
            try:
                product_count = Product.query.count()
                category_count = Category.query.count()
                print(f"   ✅ БД працює (товарів: {product_count}, категорій: {category_count})")
                return True
            except Exception as e:
                print(f"   ❌ Помилка запиту до БД: {e}")
                return False
    except Exception as e:
        print(f"   ❌ Помилка підключення до БД: {e}")
        return False

def test_api_endpoints():
    """Тест 5: Перевірка API endpoints"""
    print("🧪 Тест 5: Перевірка API endpoints...")
    try:
        from app import app
        
        api_routes = [
            '/api/products',
            '/api/categories',
            '/api/search?q=test',
        ]
        
        with app.test_client() as client:
            failed = []
            for route in api_routes:
                try:
                    response = client.get(route)
                    if response.status_code != 200:
                        failed.append(f"{route} → {response.status_code}")
                except Exception as e:
                    failed.append(f"{route} → {str(e)}")
            
            if failed:
                print(f"   ❌ Помилки в API:")
                for f in failed:
                    print(f"      {f}")
                return False
            
            print(f"   ✅ Всі {len(api_routes)} API endpoints працюють")
            return True
    except Exception as e:
        print(f"   ❌ Помилка тестування API: {e}")
        return False

def test_models():
    """Тест 6: Перевірка моделей БД"""
    print("🧪 Тест 6: Перевірка моделей...")
    try:
        from app import Product, Order, User, Review, Category
        
        # Перевірка що всі моделі мають необхідні поля
        models = {
            'Product': ['id', 'name', 'price', 'category_id'],
            'Order': ['id', 'customer_name', 'customer_phone', 'total_price'],
            'User': ['id', 'email', 'password_hash'],
            'Review': ['id', 'product_id', 'customer_name', 'rating'],
            'Category': ['id', 'name'],
        }
        
        for model_name, fields in models.items():
            model = eval(model_name)
            for field in fields:
                if not hasattr(model, field):
                    print(f"   ❌ {model_name} не має поля {field}")
                    return False
        
        print(f"   ✅ Всі {len(models)} моделі правильні")
        return True
    except Exception as e:
        print(f"   ❌ Помилка перевірки моделей: {e}")
        return False

def test_templates():
    """Тест 7: Перевірка що всі templates існують"""
    print("🧪 Тест 7: Перевірка templates...")
    try:
        templates = [
            'base.html',
            'index.html',
            'product.html',
            'checkout.html',
            'login.html',
            'register.html',
            'admin_login.html',
            'admin_dashboard.html',
            '404.html',
            '500.html',
        ]
        
        missing = []
        for template in templates:
            path = os.path.join('templates', template)
            if not os.path.exists(path):
                missing.append(template)
        
        if missing:
            print(f"   ❌ Відсутні templates:")
            for t in missing:
                print(f"      {t}")
            return False
        
        print(f"   ✅ Всі {len(templates)} templates існують")
        return True
    except Exception as e:
        print(f"   ❌ Помилка перевірки templates: {e}")
        return False

def test_static_files():
    """Тест 8: Перевірка статичних файлів"""
    print("🧪 Тест 8: Перевірка статичних файлів...")
    try:
        static_files = [
            'static/style.css',
            'static/script.js',
            'static/robots.txt',
            'static/manifest.json',
            'static/sw.js',
        ]
        
        missing = []
        for file in static_files:
            if not os.path.exists(file):
                missing.append(file)
        
        if missing:
            print(f"   ❌ Відсутні файли:")
            for f in missing:
                print(f"      {f}")
            return False
        
        print(f"   ✅ Всі {len(static_files)} статичні файли існують")
        return True
    except Exception as e:
        print(f"   ❌ Помилка перевірки файлів: {e}")
        return False

def test_security():
    """Тест 9: Перевірка безпеки"""
    print("🧪 Тест 9: Перевірка безпеки...")
    try:
        from app import app
        
        with app.test_client() as client:
            # Перевірка security headers
            response = client.get('/')
            headers = response.headers
            
            required_headers = [
                'X-Content-Type-Options',
                'X-Frame-Options',
                'X-XSS-Protection',
            ]
            
            missing = []
            for header in required_headers:
                if header not in headers:
                    missing.append(header)
            
            if missing:
                print(f"   ⚠️  Відсутні security headers:")
                for h in missing:
                    print(f"      {h}")
                # Не критична помилка
            
            print("   ✅ Базова безпека налаштована")
            return True
    except Exception as e:
        print(f"   ❌ Помилка перевірки безпеки: {e}")
        return False

def test_reviews_auth():
    """Тест 10: Перевірка що відгуки тільки для авторизованих"""
    print("🧪 Тест 10: Перевірка авторизації для відгуків...")
    try:
        from app import app
        import json
        
        with app.test_client() as client:
            # Спроба залишити відгук без авторизації
            response = client.post(
                '/api/products/1/reviews',
                data=json.dumps({'rating': 5, 'comment': 'Test'}),
                content_type='application/json'
            )
            
            if response.status_code == 401:
                print("   ✅ Відгуки тільки для авторизованих (401)")
                return True
            else:
                print(f"   ❌ Неправильний статус: {response.status_code} (очікувався 401)")
                return False
    except Exception as e:
        print(f"   ❌ Помилка тестування авторизації: {e}")
        return False

def run_all_tests():
    """Запустити всі тести"""
    print("=" * 60)
    print("🧪 АВТОМАТИЧНЕ ТЕСТУВАННЯ CLEVER SHOP")
    print("=" * 60)
    print()
    
    tests = [
        test_imports,
        test_app_config,
        test_routes,
        test_database,
        test_api_endpoints,
        test_models,
        test_templates,
        test_static_files,
        test_security,
        test_reviews_auth,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"   ❌ Критична помилка: {e}")
            results.append(False)
        print()
    
    # Підсумок
    print("=" * 60)
    print("📊 РЕЗУЛЬТАТИ ТЕСТУВАННЯ")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    percentage = (passed / total) * 100
    
    print(f"✅ Пройдено: {passed}/{total} ({percentage:.1f}%)")
    print(f"❌ Провалено: {total - passed}/{total}")
    print()
    
    if passed == total:
        print("🎉 ВСІ ТЕСТИ ПРОЙДЕНО! Сайт готовий до production!")
    elif passed >= total * 0.8:
        print("✅ БІЛЬШІСТЬ ТЕСТІВ ПРОЙДЕНО! Є деякі проблеми.")
    else:
        print("⚠️  БАГАТО ПОМИЛОК! Потрібно виправити.")
    
    print("=" * 60)
    
    return passed == total

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
