#!/usr/bin/env python3
"""
Скрипт для генерації секретів для Railway
"""

import secrets
from werkzeug.security import generate_password_hash

print("=" * 60)
print("🔐 ГЕНЕРАТОР СЕКРЕТІВ ДЛЯ RAILWAY")
print("=" * 60)
print()

# 1. SECRET_KEY
secret_key = secrets.token_hex(32)
print("1️⃣  SECRET_KEY:")
print(f"   {secret_key}")
print()

# 2. ADMIN_PASSWORD_HASH
print("2️⃣  ADMIN_PASSWORD_HASH:")
print("   Введи новий пароль для адміна:")
admin_password = input("   Пароль: ").strip()

if admin_password:
    admin_hash = generate_password_hash(admin_password)
    print(f"   {admin_hash}")
else:
    print("   ⚠️  Пароль не введено!")
print()

# 3. Інші змінні
print("3️⃣  TELEGRAM_BOT_TOKEN:")
print("   8735115362:AAHN_uuxpGm3Ut6U_Zu3Ku10xN96xC4AIko")
print()

print("4️⃣  TELEGRAM_CHAT_ID:")
print("   711331128")
print()

print("=" * 60)
print("✅ ГОТОВО!")
print("=" * 60)
print()
print("📋 Скопіюй ці значення в Railway Variables:")
print()
print(f"SECRET_KEY = {secret_key}")
if admin_password:
    print(f"ADMIN_PASSWORD_HASH = {admin_hash}")
print("TELEGRAM_BOT_TOKEN = 8735115362:AAHN_uuxpGm3Ut6U_Zu3Ku10xN96xC4AIko")
print("TELEGRAM_CHAT_ID = 711331128")
print()
print("🚀 Після додавання - зроби git push!")
