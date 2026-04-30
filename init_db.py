from app import app, db, Category

with app.app_context():
    # Тільки створює таблиці якщо їх немає — НЕ видаляє дані
    db.create_all()

    # Додати категорії тільки якщо їх немає
    if Category.query.count() == 0:
        categories = [
            Category(name='Верхній одяг'),
            Category(name='Поло'),
            Category(name='Светри'),
            Category(name='Сорочки'),
            Category(name='Джинси'),
            Category(name='Брюки'),
            Category(name='Взуття'),
            Category(name='Аксесуари'),
            Category(name='Білизна'),
        ]
        for cat in categories:
            db.session.add(cat)
        db.session.commit()
        print('✓ Категорії створено!')
    else:
        print('✓ Категорії вже існують, пропускаємо.')

    print('✓ База даних готова!')
