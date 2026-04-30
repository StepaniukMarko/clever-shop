import requests
import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import base64
import hashlib
import json
import urllib.parse

# Опціональні імпорти для безпеки (якщо встановлені)
try:
    from flask_wtf.csrf import CSRFProtect
    csrf_available = True
except ImportError:
    csrf_available = False
    print("Warning: Flask-WTF not installed. CSRF protection disabled.")

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    limiter_available = True
except ImportError:
    limiter_available = False
    print("Warning: Flask-Limiter not installed. Rate limiting disabled.")

app = Flask(__name__, template_folder='templates', static_folder='static', static_url_path='/static')

if os.environ.get('DATABASE_URL'):
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL').replace('postgres://', 'postgresql://')
else:
    basedir = os.path.abspath(os.path.dirname(__file__))
    instance_path = os.path.join(basedir, 'instance')
    os.makedirs(instance_path, exist_ok=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "shop.db")}'

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    # Для локальної розробки використовуємо тимчасовий ключ
    import secrets
    SECRET_KEY = secrets.token_hex(32)
    print("⚠️  WARNING: Using temporary SECRET_KEY! Set SECRET_KEY environment variable in production!")
app.config['SECRET_KEY'] = SECRET_KEY
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static', 'uploads')
app.config['WTF_CSRF_ENABLED'] = csrf_available
app.config['WTF_CSRF_TIME_LIMIT'] = None
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# Ініціалізація CSRF якщо доступний
if csrf_available:
    csrf = CSRFProtect(app)
else:
    # Створюємо dummy csrf об'єкт
    class DummyCSRF:
        def exempt(self, func):
            return func
    csrf = DummyCSRF()

# Ініціалізація Rate Limiter якщо доступний
if limiter_available:
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://"
    )
else:
    # Створюємо dummy limiter об'єкт
    class DummyLimiter:
        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
    limiter = DummyLimiter()

# === MODELS ===
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    products = db.relationship('Product', backref='category', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    image_url = db.Column(db.String(500))
    images = db.Column(db.Text, default='')
    stock = db.Column(db.Integer, default=0)
    brand = db.Column(db.String(100), default='Clever')
    sizes = db.Column(db.String(200), default='XS,S,M,L,XL,XXL')
    gender = db.Column(db.String(20), default='унісекс')
    type = db.Column(db.String(50), default='інше')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_images(self):
        imgs = []
        if self.image_url:
            imgs.append(self.image_url)
        if self.images:
            imgs.extend([i.strip() for i in self.images.split(',') if i.strip()])
        return imgs

    def get_sizes_with_stock(self):
        """Parse sizes field into list of (size, in_stock) tuples.
        Supports both 'XS,S,M' (all in stock) and 'XS:1,S:0,M:1' formats."""
        result = []
        if not self.sizes:
            return result
        for part in self.sizes.split(','):
            part = part.strip()
            if not part:
                continue
            if ':' in part:
                size, stock = part.split(':', 1)
                result.append((size.strip(), stock.strip() == '1'))
            else:
                result.append((part, True))
        return result

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(200), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    customer_email = db.Column(db.String(200))
    delivery = db.Column(db.String(500), default='')
    items = db.Column(db.Text, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='нове')
    payment_status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(200))
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    customer_name = db.Column(db.String(200), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    photo_url = db.Column(db.String(500))
    verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class BlogPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    slug = db.Column(db.String(300), unique=True, nullable=False)
    content = db.Column(db.Text, nullable=False)
    excerpt = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    author = db.Column(db.String(200), default='Clever Team')
    views = db.Column(db.Integer, default=0)
    published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class EmailSubscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    source = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PromoCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    discount_type = db.Column(db.String(20), nullable=False)  # 'percent' or 'fixed'
    discount_value = db.Column(db.Float, nullable=False)
    min_order_amount = db.Column(db.Float, default=0)
    max_uses = db.Column(db.Integer, default=0)  # 0 = unlimited
    current_uses = db.Column(db.Integer, default=0)
    valid_from = db.Column(db.DateTime, default=datetime.utcnow)
    valid_until = db.Column(db.DateTime)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def is_valid(self, order_amount=0):
        now = datetime.utcnow()
        if not self.active:
            return False, "Промокод неактивний"
        if self.valid_from and now < self.valid_from:
            return False, "Промокод ще не активний"
        if self.valid_until and now > self.valid_until:
            return False, "Промокод прострочений"
        if self.max_uses > 0 and self.current_uses >= self.max_uses:
            return False, "Промокод вичерпано"
        if order_amount < self.min_order_amount:
            return False, f"Мінімальна сума замовлення {self.min_order_amount} грн"
        return True, "OK"
    
    def calculate_discount(self, order_amount):
        if self.discount_type == 'percent':
            return order_amount * (self.discount_value / 100)
        else:  # fixed
            return min(self.discount_value, order_amount)

class UserBonus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    points = db.Column(db.Integer, default=0)
    total_earned = db.Column(db.Integer, default=0)
    total_spent = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# === LIQPAY INTEGRATION ===
class LiqPay:
    def __init__(self, public_key, private_key):
        self.public_key = public_key
        self.private_key = private_key
    
    def _create_signature(self, data):
        encoded_data = base64.b64encode(data.encode('utf-8')).decode('ascii')
        sign_string = self.private_key + encoded_data + self.private_key
        signature = base64.b64encode(hashlib.sha1(sign_string.encode('utf-8')).digest()).decode('ascii')
        return signature
    
    def create_payment(self, order_id, amount, description, result_url):
        params = {
            'version': '3',
            'public_key': self.public_key,
            'action': 'pay',
            'amount': str(amount),
            'currency': 'UAH',
            'description': description,
            'order_id': str(order_id),
            'result_url': result_url,
            'server_url': result_url.replace('/result/', '/callback/'),
            'language': 'uk'
        }
        
        data = base64.b64encode(json.dumps(params).encode('utf-8')).decode('ascii')
        signature = self._create_signature(json.dumps(params))
        
        return {'data': data, 'signature': signature}
    
    def verify_callback(self, data, signature):
        expected_signature = self._create_signature(base64.b64decode(data).decode('utf-8'))
        return signature == expected_signature

LIQPAY_PUBLIC_KEY = os.environ.get('LIQPAY_PUBLIC_KEY', 'sandbox_i00000000000')
LIQPAY_PRIVATE_KEY = os.environ.get('LIQPAY_PRIVATE_KEY', 'sandbox_xxxxxxxxxxxxxxxxxxxxxxxx')
liqpay = LiqPay(LIQPAY_PUBLIC_KEY, LIQPAY_PRIVATE_KEY)

# === AUTO-FIX SHOE SIZES ON STARTUP ===
def fix_shoe_sizes():
    """Fix products of type 'кросівки' that still have clothing sizes."""
    try:
        shoes = Product.query.filter_by(type='кросівки').all()
        clothing_sizes = {'XS', 'S', 'M', 'L', 'XL', 'XXL'}
        changed = 0
        for p in shoes:
            parts = [s.strip() for s in (p.sizes or '').split(',')]
            if any(s in clothing_sizes for s in parts):
                if p.gender == 'жіночий':
                    p.sizes = '36,37,38,39,40,41'
                elif p.gender == 'чоловічий':
                    p.sizes = '40,41,42,43,44,45,46'
                else:
                    p.sizes = '36,37,38,39,40,41,42,43,44,45,46'
                changed += 1
        if changed:
            db.session.commit()
    except Exception:
        pass

_shoe_sizes_fixed = False

@app.before_request
def _run_fix_once():
    global _shoe_sizes_fixed
    if not _shoe_sizes_fixed:
        _shoe_sizes_fixed = True
        fix_shoe_sizes()

# Security headers
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # CSP - дозволяємо тільки наші ресурси та необхідні зовнішні
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://www.googletagmanager.com https://connect.facebook.net https://www.liqpay.ua; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https: http:; "
        "connect-src 'self' https://api.novaposhta.ua https://www.liqpay.ua; "
        "frame-src 'self' https://www.liqpay.ua;"
    )
    response.headers['Content-Security-Policy'] = csp
    return response

# Database error handler
@app.teardown_appcontext
def shutdown_session(exception=None):
    if exception:
        db.session.rollback()
    db.session.remove()

# === ROUTES ===
@app.route('/')
def index():
    categories = Category.query.all()
    products = Product.query.all()
    return render_template('index.html', categories=categories, products=products)

@app.route('/category/<int:category_id>')
def category(category_id):
    cat = Category.query.get_or_404(category_id)
    products = Product.query.filter_by(category_id=category_id).all()
    categories = Category.query.all()
    return render_template('category.html', category=cat, products=products, categories=categories)

@app.route('/brands')
def brands():
    return render_template('brands.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contacts')
def contacts():
    return render_template('contacts.html')

@app.route('/product/<int:product_id>')
def product(product_id):
    prod = Product.query.get_or_404(product_id)
    products = Product.query.limit(8).all()
    categories = Category.query.all()
    return render_template('product.html', product=prod, categories=categories, products=products)

@app.route('/wishlist')
def wishlist():
    return render_template('wishlist.html')

@app.route('/delivery')
def delivery_page():
    return render_template('delivery.html')

@app.route('/returns')
def returns_page():
    return render_template('returns.html')

@app.route('/oferta')
def oferta_page():
    return render_template('oferta.html')

@app.route('/privacy')
def privacy_page():
    return render_template('privacy.html')

def _notify_telegram(order_id, name, phone, total, items, delivery, payment_status='очікується'):
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        print("⚠️ TELEGRAM_BOT_TOKEN not set, notifications disabled")
        return
    chat_ids = [os.environ.get('TELEGRAM_CHAT_ID', '711331128')]
    
    items_text = "\n".join([f"  • {item.get('name', 'Товар')} (×{item.get('quantity', 1)}) - {item.get('price', 0) * item.get('quantity', 1)} грн" for item in items])
    
    # Визначаємо емодзі та текст статусу оплати
    if payment_status == 'paid' or payment_status == 'оплачено':
        payment_emoji = '✅'
        payment_text = 'ОПЛАЧЕНО'
    else:
        payment_emoji = '⏳'
        payment_text = 'ОЧІКУЄТЬСЯ ОПЛАТА'
    
    text = f"""🌐 clevershop.vn.ua
━━━━━━━━━━━━━━━━━━━━
🛒 Нове замовлення #{order_id}

👤 Клієнт: {name}
📞 Телефон: {phone}
🚚 Доставка: {delivery}

📦 Товари:
{items_text}

💰 Сума: {total} грн
{payment_emoji} Оплата: {payment_text}
━━━━━━━━━━━━━━━━━━━━"""
    
    for cid in chat_ids:
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": cid, "text": text})
        except:
            pass

@app.route('/checkout', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
@csrf.exempt  # Exempt для API calls з JavaScript
def checkout():
    if request.method == 'POST':
        data = request.get_json()
        
        # Calculate total
        total = data['total']
        discount = 0
        promo_code = None
        
        # Apply promo code if provided
        if data.get('promo_code'):
            promo = PromoCode.query.filter_by(code=data['promo_code'].upper()).first()
            if promo:
                is_valid, message = promo.is_valid(total)
                if is_valid:
                    discount = promo.calculate_discount(total)
                    total -= discount
                    promo_code = promo.code
                    promo.current_uses += 1
                else:
                    return jsonify({'error': message}), 400
        
        order = Order(
            customer_name=data['name'],
            customer_phone=data['phone'],
            customer_email=data.get('email', ''),
            delivery=data.get('delivery', ''),
            items=str(data['items']),
            total_price=total,
            status='нове'
        )
        db.session.add(order)
        db.session.commit()
        
        # Award bonus points if user is logged in
        if session.get('user_id'):
            user_bonus = UserBonus.query.filter_by(user_id=session['user_id']).first()
            if not user_bonus:
                user_bonus = UserBonus(user_id=session['user_id'])
                db.session.add(user_bonus)
            
            # Award 1 point per 100 UAH spent
            points_earned = int(total / 100)
            user_bonus.points += points_earned
            user_bonus.total_earned += points_earned
            db.session.commit()
        
        # Check payment method
        if data.get('payment_method') == 'online':
            payment_data = liqpay.create_payment(
                order_id=order.id,
                amount=order.total_price,
                description=f"Замовлення #{order.id} - Clever Shop",
                result_url=url_for('payment_result', order_id=order.id, _external=True)
            )
            return jsonify({
                "success": True,
                "order_id": order.id,
                "payment_required": True,
                "payment_data": payment_data,
                "discount": discount,
                "promo_code": promo_code
            })
        else:
            # Якщо не онлайн (не повинно статися, але на всяк випадок)
            _notify_telegram(order.id, data["name"], data["phone"], total, str(data["items"]), data.get("delivery", ""), 'очікується')
            return jsonify({
                "success": True, 
                "order_id": order.id,
                "discount": discount,
                "promo_code": promo_code
            })
    return render_template('checkout.html')

@app.route('/payment/callback/<int:order_id>', methods=['POST'])
def payment_callback(order_id):
    data = request.form.get('data')
    signature = request.form.get('signature')
    
    if liqpay.verify_callback(data, signature):
        payment_info = json.loads(base64.b64decode(data).decode('utf-8'))
        order = Order.query.get(order_id)
        
        if order and payment_info['status'] == 'success':
            order.status = 'оплачено'
            order.payment_status = 'paid'
            db.session.commit()
            _notify_telegram(order.id, order.customer_name, order.customer_phone, order.total_price, order.items, order.delivery, 'paid')
    
    return jsonify({'status': 'ok'})

@app.route('/payment/result/<int:order_id>')
def payment_result(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('thankyou.html', order=order)

@app.route('/thank-you/<int:order_id>')
def thank_you(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('thankyou.html', order=order)

# === FILE UPLOAD ===
@app.route('/api/upload', methods=['POST'])
def upload_image():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    if 'image' not in request.files:
        return jsonify({'error': 'No file'}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No file'}), 400
    filename = secure_filename(str(int(datetime.utcnow().timestamp())) + '_' + file.filename)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    image_url = url_for('static', filename='uploads/' + filename)
    return jsonify({'url': image_url})

@app.route('/api/proxy-image', methods=['POST'])
def proxy_image():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    img_url = data.get('url', '')
    if not img_url:
        return jsonify({'error': 'No URL'}), 400
    
    # Якщо вже локальне — повертаємо як є
    if img_url.startswith('/static/') or img_url.startswith('/uploads/'):
        return jsonify({'url': img_url})
    
    try:
        from urllib.parse import urlparse as _up
        parsed_u = _up(img_url)
        
        # Спробуємо кілька варіантів headers
        attempts = [
            {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
                'Referer': f"{parsed_u.scheme}://{parsed_u.netloc}/",
            },
            {
                'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
                'Accept': 'image/*',
            },
            {
                'User-Agent': 'curl/7.68.0',
                'Accept': '*/*',
            },
        ]
        
        resp = None
        for hdrs in attempts:
            try:
                r = requests.get(img_url, headers=hdrs, timeout=20, stream=True, allow_redirects=True)
                if r.status_code == 200:
                    resp = r
                    break
            except:
                continue
        
        if not resp or resp.status_code != 200:
            return jsonify({'error': f'Cannot download image'}), 400
        
        content_type = resp.headers.get('content-type', 'image/jpeg').lower()
        ext = 'webp' if 'webp' in content_type else 'png' if 'png' in content_type else 'jpg'
        
        filename = f"{int(datetime.utcnow().timestamp())}_{abs(hash(img_url)) % 100000}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        with open(filepath, 'wb') as f:
            for chunk in resp.iter_content(8192):
                if chunk:
                    f.write(chunk)
        
        if os.path.getsize(filepath) < 100:
            os.remove(filepath)
            return jsonify({'error': 'Empty file'}), 400
        
        return jsonify({'url': url_for('static', filename='uploads/' + filename)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload-multiple', methods=['POST'])
def upload_multiple():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    urls = []
    files = request.files.getlist('images')
    for file in files[:8]:
        if file and file.filename:
            filename = secure_filename(str(int(datetime.utcnow().timestamp())) + '_' + file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            urls.append(url_for('static', filename='uploads/' + filename))
    return jsonify({'urls': urls})

# === ADMIN ===
@app.route('/admin/login', methods=['POST'])
@limiter.limit("5 per minute")
@csrf.exempt
def admin_login():
    password = request.form.get('password')
    ADMIN_PASSWORD_HASH = os.environ.get('ADMIN_PASSWORD_HASH')
    
    # Якщо немає хеша в змінних - використовуємо старий пароль (тимчасово)
    if not ADMIN_PASSWORD_HASH:
        print("⚠️  WARNING: ADMIN_PASSWORD_HASH not set! Using default password (INSECURE!)")
        if password == 'clever.admin.123':
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
    else:
        if check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
    
    return redirect(url_for('admin_login_page'))

@app.route('/admin/login')
def admin_login_page():
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('index'))

@app.route('/admin')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login_page'))
    categories = Category.query.all()
    products = Product.query.all()
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin_dashboard.html', categories=categories, products=products, orders=orders)

@app.route('/api/orders/<int:order_id>/status', methods=['POST'])
def update_order_status(order_id):
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    order = Order.query.get_or_404(order_id)
    data = request.get_json()
    order.status = data.get('status', order.status)
    db.session.commit()
    return jsonify({'success': True})

# === PRODUCTS API ===
@app.route('/api/products', methods=['GET', 'POST'])
def api_products():
    if request.method == 'POST':
        if not session.get('admin'):
            return jsonify({'error': 'Unauthorized'}), 401
        data = request.get_json()
        image_urls = data.get('image_urls', [])
        main_image = image_urls[0] if image_urls else data.get('image_url', '')
        extra_images = ','.join(image_urls[1:]) if len(image_urls) > 1 else ''
        product = Product(
            name=data['name'],
            description=data.get('description', ''),
            price=data['price'],
            category_id=data['category_id'],
            image_url=main_image,
            images=extra_images,
            stock=data.get('stock', 0),
            brand=data.get('brand', 'Clever'),
            sizes=data.get('sizes', 'XS,S,M,L,XL,XXL'),
            gender=data.get('gender', 'унісекс'),
            type=data.get('type', 'інше')
        )
        db.session.add(product)
        db.session.commit()
        return jsonify({'id': product.id})
    return jsonify([{'id': p.id, 'name': p.name, 'price': p.price, 'image_url': p.image_url or '', 'brand': p.brand} for p in Product.query.all()])

@app.route('/api/products/<int:product_id>', methods=['PUT', 'DELETE'])
def api_product(product_id):
    product = Product.query.get_or_404(product_id)
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    if request.method == 'PUT':
        data = request.get_json()
        product.name = data.get('name', product.name)
        product.price = data.get('price', product.price)
        product.stock = data.get('stock', product.stock)
        product.brand = data.get('brand', product.brand)
        product.sizes = data.get('sizes', product.sizes)
        product.gender = data.get('gender', product.gender)
        product.type = data.get('type', product.type)
        if 'image_url' in data:
            product.image_url = data['image_url']
        db.session.commit()
        return jsonify({'success': True})
    if request.method == 'DELETE':
        db.session.delete(product)
        db.session.commit()
        return jsonify({'success': True})

# === PRODUCT PARSER ===
from bs4 import BeautifulSoup
import re
import json as json_lib
from urllib.parse import urlparse

def _extract_json_ld_images(soup):
    """Витягує зображення з JSON-LD"""
    images = []
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            raw = script.string
            if not raw:
                continue
            data = json_lib.loads(raw)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                for key in ['image', 'images', 'photo', 'thumbnail']:
                    val = item.get(key)
                    if isinstance(val, list):
                        images.extend([v if isinstance(v, str) else v.get('url', '') for v in val])
                    elif isinstance(val, str):
                        images.append(val)
                    elif isinstance(val, dict):
                        images.append(val.get('url', ''))
        except:
            pass
    return images

def _extract_meta_images(soup):
    """Витягує зображення з og:image та twitter:image"""
    images = []
    for prop in ['og:image', 'og:image:secure_url', 'twitter:image']:
        for tag in soup.find_all('meta', property=prop):
            c = tag.get('content', '')
            if c:
                images.append(c)
        for tag in soup.find_all('meta', attrs={'name': prop}):
            c = tag.get('content', '')
            if c:
                images.append(c)
    return images

def _extract_all_img_tags(soup, url):
    """Витягує зображення з img тегів"""
    images = []
    domain = urlparse(url).netloc
    for img in soup.find_all('img'):
        src = (img.get('src') or img.get('data-src') or
               img.get('data-lazy-src') or img.get('data-original') or
               img.get('data-zoom-image') or img.get('data-large') or '')
        if not src:
            continue
        # Пропускаємо маленькі/службові
        if any(skip in src.lower() for skip in ['logo', 'icon', 'sprite', 'placeholder', '1x1', 'pixel', 'blank', 'loading', 'spinner']):
            continue
        # Беремо тільки достатньо великі зображення (за URL-патернами)
        if any(kw in src.lower() for kw in ['product', 'item', 'goods', 'media', 'cdn', 'image', 'photo', 'img', 'upload', 'catalog', 'p/']):
            if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                images.append(src)
    return images

def _clean_images(images, base_url):
    """Очищає та дедуплікує список зображень"""
    parsed_base = urlparse(base_url)
    clean = []
    seen = set()
    
    # Патерни що точно є логотипами/іконками — пропускаємо
    skip_patterns = [
        'logo', 'icon', 'sprite', 'placeholder', '1x1', 'pixel', 'blank',
        'banner', 'favicon', 'brand', 'puma', 'champion', 'newbalance',
        'new-balance', 'icepeak', 'lagoa', 'arena', 'eastpeak', 'east-peak',
        'nike-logo', 'adidas-logo', 'jordan-logo',
        '/brands/', '/brand/', '/logos/', '/logo/',
        'payment', 'social', 'flag', 'arrow', 'button', 'bg-',
    ]
    
    # Мінімальний розмір — відкидаємо маленькі зображення за URL
    skip_size_patterns = ['_xs', '_sm', '_thumb', 'thumbnail', '50x50', '100x100', '32x32', '64x64']
    
    for img in images:
        if not img or not isinstance(img, str):
            continue
        img = img.strip()
        if img.startswith('//'):
            img = 'https:' + img
        elif img.startswith('/'):
            img = f"{parsed_base.scheme}://{parsed_base.netloc}{img}"
        elif not img.startswith('http'):
            continue
        
        img_lower = img.lower()
        
        # Пропускаємо службові
        if any(skip in img_lower for skip in skip_patterns):
            continuenue
        if any(skip in img_lower for skip in skip_size_patterns):
            continue
        
        if img not in seen:
            seen.add(img)
            clean.append(img)
    
    # Shopify — прибираємо query параметри з URL зображень (вони заважають)
    clean2 = []
    for img in clean:
        if 'cdn.shopify.com' in img and '?' in img:
            img = img.split('?')[0]
        clean2.append(img)
    
    # Дедуплікуємо після очищення
    seen2 = set()
    result = []
    for img in clean2:
        if img not in seen2:
            seen2.add(img)
            result.append(img)
    
    return result[:8]

def extract_images_from_url(url, soup, html):
    """Витягує всі фотки товару — універсальний метод"""
    images = []
    
    # 1. JSON-LD (найнадійніший)
    images.extend(_extract_json_ld_images(soup))
    
    # 2. Meta og:image — завжди фото товару, ставимо першим
    og_imgs = _extract_meta_images(soup)
    if og_imgs and not images:
        images.extend(og_imgs)
    
    # 3. Специфічні патерни для популярних магазинів
    url_lower = url.lower()
    
    if 'massimodutti' in url_lower:
        # Massimo Dutti зберігає фото в JSON в тегу script
        for script in soup.find_all('script'):
            text = script.string or ''
            if 'colorImages' in text or 'imageList' in text or '"images"' in text:
                try:
                    # Шукаємо масиви URL зображень
                    found = re.findall(r'https://[^"\']+(?:massimodutti|inditex)[^"\']*\.(?:jpg|jpeg|png|webp)', text)
                    images.extend(found)
                except:
                    pass
    
    elif 'zalando' in url_lower:
        for img in soup.find_all('img', {'data-testid': re.compile(r'image', re.I)}):
            src = img.get('src') or img.get('data-src', '')
            if src:
                images.append(src)
        # Zalando також зберігає в __NEXT_DATA__
        for script in soup.find_all('script', id='__NEXT_DATA__'):
            try:
                data = json_lib.loads(script.string)
                text = json_lib.dumps(data)
                found = re.findall(r'https://img[^"\']+\.(?:jpg|jpeg|png|webp)', text)
                images.extend(found[:8])
            except:
                pass
    
    elif 'aboutyou' in url_lower:
        for script in soup.find_all('script', id='__NEXT_DATA__'):
            try:
                data = json_lib.loads(script.string)
                text = json_lib.dumps(data)
                found = re.findall(r'https://[^"\']+aboutyou[^"\']*\.(?:jpg|jpeg|png|webp)', text)
                images.extend(found[:8])
            except:
                pass
    
    elif 'asos' in url_lower:
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if 'images.asos-media.com' in src:
                images.append(src)
        for script in soup.find_all('script'):
            text = script.string or ''
            if 'asos-media.com' in text:
                found = re.findall(r'https://[^"\']+asos-media\.com[^"\']*\.(?:jpg|jpeg|png|webp)', text)
                images.extend(found[:8])
    
    elif 'farfetch' in url_lower:
        for script in soup.find_all('script'):
            text = script.string or ''
            if 'farfetch' in text and ('images' in text or 'photos' in text):
                found = re.findall(r'https://[^"\']+farfetch[^"\']*\.(?:jpg|jpeg|png|webp)', text)
                images.extend(found[:8])
    
    elif 'mango' in url_lower:
        for script in soup.find_all('script'):
            text = script.string or ''
            if 'mango' in text.lower() and '.jpg' in text:
                found = re.findall(r'https://[^"\']+mango[^"\']*\.(?:jpg|jpeg|png|webp)', text)
                images.extend(found[:8])
    
    elif 'hm.com' in url_lower or 'h&m' in url_lower:
        for img in soup.find_all('img'):
            src = img.get('src', '') or img.get('data-src', '')
            if 'lp2.hm.com' in src or 'hmgroup' in src:
                images.append(src)
    
    elif 'shopify' in url_lower or 'myshopify' in url_lower or '/products/' in url_lower:
        # Shopify має JSON API: /products/handle.json
        try:
            from urllib.parse import urlparse as _up
            parsed_u = _up(url)
            # Беремо handle з URL і запитуємо JSON API
            path_parts = parsed_u.path.rstrip('/').split('/')
            if 'products' in path_parts:
                idx = path_parts.index('products')
                if idx + 1 < len(path_parts):
                    handle = path_parts[idx + 1].split('?')[0]
                    json_url = f"{parsed_u.scheme}://{parsed_u.netloc}/products/{handle}.json"
                    r = requests.get(json_url, headers={
                        'User-Agent': 'Mozilla/5.0',
                        'Accept': 'application/json'
                    }, timeout=10)
                    if r.status_code == 200:
                        pdata = r.json().get('product', {})
                        for img in pdata.get('images', []):
                            src = img.get('src', '')
                            if src:
                                # Прибираємо query параметри
                                src = src.split('?')[0]
                                images.append(src)
        except:
            pass
        
        # Fallback — шукаємо в HTML
        if not images:
            for script in soup.find_all('script', type='application/json'):
                try:
                    d = json_lib.loads(script.string)
                    text = json_lib.dumps(d)
                    found = re.findall(r'https://cdn\.shopify\.com/s/files/[^\s"\'<>\\]+\.(?:jpg|jpeg|png|webp)', text)
                    images.extend([f.split('?')[0] for f in found])
                except:
                    pass
        
        if not images:
            for script in soup.find_all('script'):
                text = script.string or ''
                if 'cdn.shopify.com' in text:
                    found = re.findall(r'https://cdn\.shopify\.com/s/files/[^\s"\'<>\\]+\.(?:jpg|jpeg|png|webp)', text)
                    images.extend([f.split('?')[0] for f in found])
        
        if not images:
            images.extend(_extract_meta_images(soup))

    elif 'megasport' in url_lower:
        # Megasport зберігає фото товару в CDN з патерном /products/ або /catalog/
        full_html = str(soup)
        # Шукаємо URL фото товару — вони містять /products/ або числовий ID
        product_patterns = [
            r'https://[^\s"\'<>\\]+(?:/products?/|/catalog/|/items?/)[^\s"\'<>\\]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'<>\\]*)?',
            r'https://cdn[^\s"\'<>\\]+megasport[^\s"\'<>\\]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'<>\\]*)?',
            r'https://[^\s"\'<>\\]+megasport[^\s"\'<>\\]+(?:/\d+/)[^\s"\'<>\\]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'<>\\]*)?',
        ]
        for pattern in product_patterns:
            found = re.findall(pattern, full_html)
            images.extend(found)
        
        # og:image як надійний fallback
        if not images:
            images.extend(_extract_meta_images(soup))
        
        # img теги з data-атрибутами
        if not images:
            for img in soup.find_all('img'):
                for attr in ['src', 'data-src', 'data-original', 'data-zoom-image', 'data-large-image']:
                    src = img.get(attr, '')
                    if src and any(ext in src for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                        if not any(skip in src.lower() for skip in ['logo', 'icon', 'banner', 'brand']):
                            images.append(src)
                            break
    
    elif 'zara' in url_lower:
        for script in soup.find_all('script'):
            text = script.string or ''
            if 'zara' in text.lower() and 'images' in text:
                found = re.findall(r'https://[^"\']+static\.zara[^"\']*\.(?:jpg|jpeg|png|webp)', text)
                images.extend(found[:8])
    
    # 4. Загальний fallback — img теги
    if not images:
        images.extend(_extract_all_img_tags(soup, url))
    
    # 5. Шукаємо будь-які URL зображень в скриптах (останній шанс)
    if not images:
        for script in soup.find_all('script'):
            text = script.string or ''
            if len(text) > 100:
                found = re.findall(r'https://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'<>]*)?', text)
                for f in found:
                    if not any(skip in f.lower() for skip in ['logo', 'icon', 'sprite', '1x1', 'pixel']):
                        images.append(f)
                if images:
                    break
    
    # 6. Якщо Jina повернув текст — шукаємо URL зображень прямо в тексті сторінки
    if not images:
        full_text = str(soup)
        # Спочатку Shopify CDN
        found = re.findall(r'https://cdn\.shopify\.com/s/files/[^\s"\'<>\\]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'<>\\]*)?', full_text)
        images.extend(found)
    
    if not images:
        full_text = str(soup)
        found = re.findall(r'https://[^\s"\'<>\\]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'<>\\]*)?', full_text)
        for f in found:
            if not any(skip in f.lower() for skip in ['logo', 'icon', 'sprite', '1x1', 'pixel', 'banner', 'favicon']):
                images.append(f)
    
    return _clean_images(images, url)


def _fetch_with_fallback(url):
    """Спробує отримати HTML різними способами"""
    
    url_lower = url.lower()
    
    # JS-сайти — одразу через Jina (рендерить JS)
    js_sites = ['megasport', 'massimodutti', 'zara', 'hm.com', 'farfetch', 
                'aboutyou', 'zalando', 'asos', 'mango', 'lacoste', 
                'calvinklein', 'tommyhilfiger', 'boss', 'diesel',
                'shopify', 'myshopify', 'quellogiusto', 'sneakers']
    
    use_jina_first = any(s in url_lower for s in js_sites)
    
    if use_jina_first:
        try:
            jina_url = f'https://r.jina.ai/{url}'
            resp = requests.get(jina_url, headers={
                'Accept': 'text/html,application/xhtml+xml',
                'X-Return-Format': 'html'
            }, timeout=30)
            if resp.status_code == 200 and len(resp.text) > 500:
                return resp.text, 'jina'
        except Exception:
            pass
    
    # Звичайний запит з реалістичними headers
    headers_list = [
        {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        },
        {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        {
            'User-Agent': 'Googlebot/2.1 (+http://www.google.com/bot.html)',
            'Accept': 'text/html',
        }
    ]
    
    for headers in headers_list:
        try:
            resp = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
            if resp.status_code == 200 and len(resp.text) > 500:
                return resp.text, None
        except Exception:
            continue
    
    # Jina як останній fallback
    if not use_jina_first:
        try:
            jina_url = f'https://r.jina.ai/{url}'
            resp = requests.get(jina_url, headers={
                'Accept': 'text/html,application/xhtml+xml',
                'X-Return-Format': 'html'
            }, timeout=30)
            if resp.status_code == 200:
                return resp.text, 'jina'
        except Exception:
            pass
    
    return None, 'failed'


def _translate_to_ukrainian(text):
    """Translate text to Ukrainian using Google Translate free API."""
    if not text or not text.strip():
        return text
    try:
        encoded = urllib.parse.quote(text)
        url = f'https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=uk&dt=t&q={encoded}'
        resp = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code == 200:
            data = resp.json()
            translated = ''.join(part[0] for part in data[0] if part[0])
            return translated
    except Exception:
        pass
    return text


@app.route('/api/parse-url', methods=['POST'])
def parse_product_url():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    url = data.get('url', '')
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    try:
        html, source = _fetch_with_fallback(url)
        
        if not html:
            return jsonify({'error': f'Не вдалося завантажити сторінку. Спробуйте інше посилання.'}), 400
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Name
        name = ''
        og_title = soup.find('meta', property='og:title')
        if og_title:
            name = og_title.get('content', '')
        if not name:
            for sel in ['h1', 'title']:
                t = soup.find(sel)
                if t:
                    name = t.get_text(strip=True)
                    break
        # Очищаємо назву від назви сайту
        if ' | ' in name:
            name = name.split(' | ')[0].strip()
        if ' - ' in name:
            name = name.split(' - ')[0].strip()
        
        # Description
        description = ''
        og_desc = soup.find('meta', property='og:description')
        if og_desc:
            description = og_desc.get('content', '')
        if not description:
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                description = meta_desc.get('content', '')
        
        # Images
        images = extract_images_from_url(url, soup, html)
        
        # Brand detection
        brand = ''
        brands_map = {
            'massimodutti': 'Massimo Dutti',
            'massimo dutti': 'Massimo Dutti',
            'calvinklein': 'Calvin Klein',
            'calvin klein': 'Calvin Klein',
            'calvinkleinjeans': 'Calvin Klein',
            'tommyhilfiger': 'Tommy Hilfiger',
            'tommy hilfiger': 'Tommy Hilfiger',
            'ralphlauren': 'Polo Ralph Lauren',
            'polo ralph lauren': 'Polo Ralph Lauren',
            'ralph lauren': 'Polo Ralph Lauren',
            'karllagerfeld': 'Karl Lagerfeld',
            'karl lagerfeld': 'Karl Lagerfeld',
            'premiata': 'Premiata',
            'armaniexchange': 'Armani Exchange',
            'armani exchange': 'Armani Exchange',
            'hugoboss': 'Boss',
            'hugo boss': 'Boss',
            '/boss/': 'Boss',
            'levis': "Levi's",
            "levi's": "Levi's",
            'diesel': 'Diesel',
            'lacoste': 'Lacoste',
            'mango': 'Mango',
            'victoriassecret': "Victoria's Secret",
            "victoria's secret": "Victoria's Secret",
            'michaelkors': 'Michael Kors',
            'michael kors': 'Michael Kors',
        }
        url_lower = url.lower()
        name_lower = name.lower()
        for key, val in brands_map.items():
            if key in url_lower or key in name_lower:
                brand = val
                break
        
        # Price — з JSON-LD
        price = 0
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                d = json_lib.loads(script.string)
                items = d if isinstance(d, list) else [d]
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    offers = item.get('offers', {})
                    if isinstance(offers, dict):
                        p = offers.get('price') or offers.get('lowPrice')
                        if p:
                            price = float(str(p).replace(',', '.'))
                            break
                    elif isinstance(offers, list) and offers:
                        p = offers[0].get('price')
                        if p:
                            price = float(str(p).replace(',', '.'))
                            break
                if price:
                    break
            except:
                pass
        
        # Price — з meta тегів
        if not price:
            for prop in ['product:price:amount', 'og:price:amount']:
                tag = soup.find('meta', property=prop)
                if tag:
                    try:
                        price = float(tag.get('content', '0').replace(',', '.'))
                        break
                    except:
                        pass
        
        # Translate name and description to Ukrainian
        name = _translate_to_ukrainian(name)
        description = _translate_to_ukrainian(description)

        return jsonify({
            'success': True,
            'name': name[:200],
            'description': description[:500],
            'images': images,
            'image_url': images[0] if images else '',
            'brand': brand,
            'price': price,
            'source': source or 'direct'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# === USER AUTH ===
@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
@csrf.exempt
def register():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        email = data.get('email')
        password = data.get('password')
        name = data.get('name', '')
        
        if User.query.filter_by(email=email).first():
            if request.is_json:
                return jsonify({'error': 'Email вже зареєстрований'}), 400
            return render_template('register.html', error='Email вже зареєстрований')
        
        user = User(email=email, password_hash=generate_password_hash(password), name=name)
        db.session.add(user)
        db.session.commit()
        session['user_id'] = user.id
        session['user_name'] = user.name or user.email
        
        if request.is_json:
            return jsonify({'success': True})
        return redirect(url_for('account'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
@csrf.exempt
def login():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        email = data.get('email')
        password = data.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['user_name'] = user.name or user.email
            
            # Redirect до попередньої сторінки якщо є
            redirect_url = request.args.get('redirect') or url_for('account')
            
            if request.is_json:
                return jsonify({'success': True, 'redirect': redirect_url})
            return redirect(redirect_url)
        
        if request.is_json:
            return jsonify({'error': 'Невірний email або пароль'}), 400
        return render_template('login.html', error='Невірний email або пароль')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    return redirect(url_for('index'))

@app.route('/account')
def account():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    orders = Order.query.filter_by(customer_email=user.email).order_by(Order.created_at.desc()).all()
    return render_template('account.html', user=user, orders=orders)

@app.route('/account/update', methods=['POST'])
def account_update():
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    data = request.get_json()
    user.name = data.get('name', user.name)
    user.phone = data.get('phone', user.phone)
    db.session.commit()
    session['user_name'] = user.name
    return jsonify({'success': True})

with app.app_context():
    db.create_all()
    # Create default category if none exists
    if not Category.query.first():
        cat = Category(name='Одяг')
        db.session.add(cat)
        db.session.commit()

# === EMAIL SUBSCRIPTION ===
@app.route('/api/subscribe', methods=['POST'])
@limiter.limit("3 per hour")
@csrf.exempt
def subscribe_email():
    data = request.get_json()
    email = data.get('email')
    
    if not email:
        return jsonify({'error': 'Email обов\'язковий'}), 400
    
    existing = EmailSubscriber.query.filter_by(email=email).first()
    if existing:
        return jsonify({'message': 'Ви вже підписані!'}), 200
    
    subscriber = EmailSubscriber(email=email, source=data.get('source', 'popup'))
    db.session.add(subscriber)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Дякуємо за підписку!'})

# === REVIEWS ===
@app.route('/api/products/<int:product_id>/reviews', methods=['GET', 'POST'])
@limiter.limit("10 per hour", methods=["POST"])
@csrf.exempt
def product_reviews(product_id):
    if request.method == 'POST':
        # Перевірка авторизації
        if not session.get('user_id'):
            return jsonify({'error': 'Щоб залишити відгук, потрібно увійти в акаунт'}), 401
        
        # Отримуємо дані користувача
        user = User.query.get(session['user_id'])
        if not user:
            return jsonify({'error': 'Користувача не знайдено'}), 404
        
        # Перевіряємо чи користувач вже залишав відгук на цей товар
        existing_review = Review.query.filter_by(
            product_id=product_id,
            customer_name=user.name or user.email
        ).first()
        
        if existing_review:
            return jsonify({'error': 'Ви вже залишили відгук на цей товар'}), 400
        
        data = request.get_json()
        
        # Перевіряємо чи користувач купував цей товар
        has_purchased = Order.query.filter_by(
            customer_email=user.email
        ).filter(
            Order.items.like(f'%"id": {product_id}%')
        ).first()
        
        review = Review(
            product_id=product_id,
            customer_name=user.name or user.email.split('@')[0],
            rating=data['rating'],
            comment=data.get('comment', ''),
            photo_url=data.get('photo_url', ''),
            verified=bool(has_purchased)  # Позначка "Підтверджена покупка"
        )
        db.session.add(review)
        db.session.commit()
        return jsonify({'success': True, 'verified': bool(has_purchased)})
    
    reviews = Review.query.filter_by(product_id=product_id).order_by(Review.created_at.desc()).all()
    return jsonify([{
        'id': r.id,
        'name': r.customer_name,
        'rating': r.rating,
        'comment': r.comment,
        'photo_url': r.photo_url,
        'verified': r.verified,
        'created_at': r.created_at.strftime('%d.%m.%Y')
    } for r in reviews])

# === BLOG ===
@app.route('/blog')
def blog_list():
    posts = BlogPost.query.filter_by(published=True).order_by(BlogPost.created_at.desc()).all()
    return render_template('blog.html', posts=posts)

@app.route('/blog/<slug>')
def blog_post(slug):
    post = BlogPost.query.filter_by(slug=slug, published=True).first_or_404()
    post.views += 1
    db.session.commit()
    return render_template('blog_post.html', post=post)

# === PROMO CODES ===
@app.route('/api/promo/validate', methods=['POST'])
def validate_promo():
    data = request.get_json()
    code = data.get('code', '').upper()
    order_amount = float(data.get('amount', 0))
    
    promo = PromoCode.query.filter_by(code=code).first()
    if not promo:
        return jsonify({'valid': False, 'message': 'Промокод не знайдено'}), 404
    
    is_valid, message = promo.is_valid(order_amount)
    if not is_valid:
        return jsonify({'valid': False, 'message': message}), 400
    
    discount = promo.calculate_discount(order_amount)
    return jsonify({
        'valid': True,
        'discount': discount,
        'discount_type': promo.discount_type,
        'discount_value': promo.discount_value,
        'new_total': order_amount - discount
    })

@app.route('/api/promo/create', methods=['POST'])
def create_promo():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    promo = PromoCode(
        code=data['code'].upper(),
        discount_type=data['discount_type'],
        discount_value=float(data['discount_value']),
        min_order_amount=float(data.get('min_order_amount', 0)),
        max_uses=int(data.get('max_uses', 0)),
        valid_until=datetime.strptime(data['valid_until'], '%Y-%m-%d') if data.get('valid_until') else None
    )
    db.session.add(promo)
    db.session.commit()
    return jsonify({'success': True, 'id': promo.id})

@app.route('/api/promo/list', methods=['GET'])
def list_promos():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    promos = PromoCode.query.order_by(PromoCode.created_at.desc()).all()
    return jsonify([{
        'id': p.id,
        'code': p.code,
        'discount_type': p.discount_type,
        'discount_value': p.discount_value,
        'current_uses': p.current_uses,
        'max_uses': p.max_uses,
        'active': p.active,
        'valid_until': p.valid_until.strftime('%Y-%m-%d') if p.valid_until else None
    } for p in promos])

# === BONUS SYSTEM ===
@app.route('/api/bonus/balance', methods=['GET'])
def bonus_balance():
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_bonus = UserBonus.query.filter_by(user_id=session['user_id']).first()
    if not user_bonus:
        return jsonify({'points': 0, 'total_earned': 0, 'total_spent': 0})
    
    return jsonify({
        'points': user_bonus.points,
        'total_earned': user_bonus.total_earned,
        'total_spent': user_bonus.total_spent
    })

@app.route('/api/bonus/spend', methods=['POST'])
def spend_bonus():
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    points_to_spend = int(data.get('points', 0))
    
    user_bonus = UserBonus.query.filter_by(user_id=session['user_id']).first()
    if not user_bonus or user_bonus.points < points_to_spend:
        return jsonify({'error': 'Недостатньо бонусів'}), 400
    
    # 1 point = 1 UAH discount
    discount = points_to_spend
    user_bonus.points -= points_to_spend
    user_bonus.total_spent += points_to_spend
    db.session.commit()
    
    return jsonify({'success': True, 'discount': discount, 'remaining_points': user_bonus.points})

# === CATEGORIES API ===
@app.route('/api/categories', methods=['GET'])
def api_categories():
    categories = Category.query.all()
    return jsonify([{'id': c.id, 'name': c.name} for c in categories])

# === SEARCH API ===
@app.route('/api/search', methods=['GET'])
def search_products():
    query = request.args.get('q', '').lower()
    if not query or len(query) < 2:
        return jsonify([])
    
    products = Product.query.filter(
        db.or_(
            Product.name.ilike(f'%{query}%'),
            Product.brand.ilike(f'%{query}%'),
            Product.description.ilike(f'%{query}%')
        )
    ).limit(20).all()
    
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'brand': p.brand,
        'price': p.price,
        'image_url': p.image_url or ''
    } for p in products])
def search_products():
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify([])
    
    products = Product.query.filter(
        (Product.name.ilike(f'%{query}%')) | 
        (Product.brand.ilike(f'%{query}%')) |
        (Product.description.ilike(f'%{query}%'))
    ).limit(10).all()
    
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'brand': p.brand,
        'price': p.price,
        'image_url': p.image_url or '',
        'stock': p.stock
    } for p in products])

# === SITEMAP ===
@app.route('/sitemap.xml')
def sitemap():
    from flask import make_response
    
    pages = []
    # Статичні сторінки
    static_pages = ['index', 'brands', 'contacts', 'delivery_page', 'returns_page', 'oferta_page', 'privacy_page', 'blog_list']
    for page in static_pages:
        pages.append({
            'loc': url_for(page, _external=True),
            'lastmod': datetime.utcnow().strftime('%Y-%m-%d'),
            'changefreq': 'weekly',
            'priority': '0.8'
        })
    
    # Товари
    products = Product.query.all()
    for product in products:
        pages.append({
            'loc': url_for('product', product_id=product.id, _external=True),
            'lastmod': product.created_at.strftime('%Y-%m-%d'),
            'changefreq': 'daily',
            'priority': '1.0'
        })
    
    # Блог
    posts = BlogPost.query.filter_by(published=True).all()
    for post in posts:
        pages.append({
            'loc': url_for('blog_post', slug=post.slug, _external=True),
            'lastmod': post.created_at.strftime('%Y-%m-%d'),
            'changefreq': 'monthly',
            'priority': '0.6'
        })
    
    sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    for page in pages:
        sitemap_xml += '  <url>\n'
        sitemap_xml += f'    <loc>{page["loc"]}</loc>\n'
        sitemap_xml += f'    <lastmod>{page["lastmod"]}</lastmod>\n'
        sitemap_xml += f'    <changefreq>{page["changefreq"]}</changefreq>\n'
        sitemap_xml += f'    <priority>{page["priority"]}</priority>\n'
        sitemap_xml += '  </url>\n'
    
    sitemap_xml += '</urlset>'
    
    response = make_response(sitemap_xml)
    response.headers['Content-Type'] = 'application/xml'
    return response

# === ERROR HANDLERS ===
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403

if __name__ == '__main__':
    with app.app_context():
        fix_shoe_sizes()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
