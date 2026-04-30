# 🚂 НАЛАШТУВАННЯ RAILWAY

## ⚠️ ВАЖЛИВО! Додай ці змінні оточення в Railway:

### Крок 1: Відкрий Railway
1. Перейди на https://railway.app
2. Вибери свій проект
3. Перейди в **Variables** (ліва панель)

### Крок 2: Додай змінні

#### 1. SECRET_KEY (ОБОВ'ЯЗКОВО!)
```
SECRET_KEY = <згенеруй_випадковий_ключ>
```

**Як згенерувати:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

#### 2. ADMIN_PASSWORD_HASH (ОБОВ'ЯЗКОВО!)
```
ADMIN_PASSWORD_HASH = <хеш_твого_пароля>
```

**Як згенерувати:**
```bash
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('твій_новий_пароль'))"
```

**Замість `твій_новий_пароль` введи свій пароль!**

#### 3. TELEGRAM_BOT_TOKEN (ОБОВ'ЯЗКОВО!)
```
TELEGRAM_BOT_TOKEN = 8735115362:AAHN_uuxpGm3Ut6U_Zu3Ku10xN96xC4AIko
```

#### 4. TELEGRAM_CHAT_ID (ОБОВ'ЯЗКОВО!)
```
TELEGRAM_CHAT_ID = 711331128
```

#### 5. LIQPAY_PUBLIC_KEY (якщо є)
```
LIQPAY_PUBLIC_KEY = твій_публічний_ключ
```

#### 6. LIQPAY_PRIVATE_KEY (якщо є)
```
LIQPAY_PRIVATE_KEY = твій_приватний_ключ
```

#### 7. DATABASE_URL (автоматично створюється Railway)
```
Не треба додавати вручну - Railway створить автоматично
```

---

## 📝 Приклад як це виглядає в Railway:

```
SECRET_KEY = a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6
ADMIN_PASSWORD_HASH = pbkdf2:sha256:260000$abc123$def456...
TELEGRAM_BOT_TOKEN = 8735115362:AAHN_uuxpGm3Ut6U_Zu3Ku10xN96xC4AIko
TELEGRAM_CHAT_ID = 711331128
LIQPAY_PUBLIC_KEY = sandbox_i00000000000
LIQPAY_PRIVATE_KEY = sandbox_xxxxxxxxxxxxxxxxxxxxxxxx
```

---

## ✅ Після додавання змінних:

1. Railway автоматично перезапустить додаток
2. Зачекай 1-2 хвилини
3. Перевір що сайт працює
4. Спробуй увійти в admin панель з новим паролем

---

## 🆘 Якщо щось не працює:

### Помилка: "SECRET_KEY environment variable must be set"
**Рішення:** Додай SECRET_KEY в Railway Variables

### Помилка: "Admin login disabled"
**Рішення:** Додай ADMIN_PASSWORD_HASH в Railway Variables

### Telegram сповіщення не приходять
**Рішення:** Перевір що TELEGRAM_BOT_TOKEN правильний

---

## 🎉 Готово!

Після налаштування всіх змінних твій сайт буде **безпечним** і готовим до production! 🚀
