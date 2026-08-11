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
import re
import html as html_module

# === TRANSLITERATION UTILITY ===
TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'h', 'ґ': 'g',
    'д': 'd', 'е': 'e', 'є': 'ye', 'ж': 'zh', 'з': 'z',
    'и': 'y', 'і': 'i', 'ї': 'yi', 'й': 'y', 'к': 'k',
    'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p',
    'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f',
    'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ь': '', 'ю': 'yu', 'я': 'ya', 'ъ': '',
}

def transliterate_to_slug(text):
    """Convert Ukrainian text to URL-safe slug."""
    text = text.lower().strip()
    result = []
    for char in text:
        if char in TRANSLIT_MAP:
            result.append(TRANSLIT_MAP[char])
        elif char.isascii() and (char.isalnum() or char == '-'):
            result.append(char)
        elif char == ' ' or char == '_':
            result.append('-')
    slug = '-'.join(filter(None, ''.join(result).split('-')))
    return slug

# === RICH DESCRIPTION PARSER ===
SECTION_ICONS = {
    'тканина': '🧵', 'матеріал': '🧵',
    'поради': '💡', 'стиль': '👔',
    'переваги': '⭐', 'бренд': '🏷️',
    'догляд': '🧼', 'розмір': '📏',
}

def render_rich_description(text):
    """Convert markdown-like description to structured HTML.

    Supports:
    - ## Section headers (with icons based on keyword mapping)
    - **bold text**
    - - bullet lists (lines starting with -)
    - Paragraph breaks (double newline)

    Escapes HTML entities in user text before applying formatting (XSS prevention).
    Returns styled placeholder when description is empty/None.
    """
    if not text or not text.strip():
        return '<div class="rich-description"><p class="rich-description__placeholder">Опис скоро буде додано</p></div>'

    # Escape HTML entities first for XSS prevention
    text = html_module.escape(text)

    lines = text.split('\n')
    html_parts = []
    current_list_items = []
    current_paragraph_lines = []

    def flush_paragraph():
        if current_paragraph_lines:
            para_text = ' '.join(current_paragraph_lines)
            # Apply bold formatting
            para_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', para_text)
            html_parts.append(f'<p>{para_text}</p>')
            current_paragraph_lines.clear()

    def flush_list():
        if current_list_items:
            items_html = ''.join(f'<li>{item}</li>' for item in current_list_items)
            html_parts.append(f'<ul>{items_html}</ul>')
            current_list_items.clear()

    for line in lines:
        stripped = line.strip()

        # Empty line = paragraph break
        if not stripped:
            flush_list()
            flush_paragraph()
            continue

        # Section header: ## Title
        if stripped.startswith('## '):
            flush_list()
            flush_paragraph()
            title = stripped[3:].strip()
            # Find matching icon
            icon = ''
            title_lower = title.lower()
            for keyword, emoji in SECTION_ICONS.items():
                if keyword in title_lower:
                    icon = emoji + ' '
                    break
            html_parts.append(f'<h4 class="rich-description__heading">{icon}{title}</h4>')
            continue

        # Bullet list item: - text
        if stripped.startswith('- '):
            flush_paragraph()
            item_text = stripped[2:].strip()
            # Apply bold formatting
            item_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', item_text)
            current_list_items.append(item_text)
            continue

        # Regular text line - accumulate for paragraph
        flush_list()
        current_paragraph_lines.append(stripped)

    # Flush remaining content
    flush_list()
    flush_paragraph()

    return '<div class="rich-description">' + ''.join(html_parts) + '</div>'

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

# Register Jinja2 template filters
app.jinja_env.filters['render_rich_description'] = render_rich_description

def ensure_https(url):
    """Convert http:// URLs to https:// to prevent mixed content issues."""
    if url and isinstance(url, str):
        return url.replace('http://', 'https://')
    return url or ''

app.jinja_env.filters['ensure_https'] = ensure_https

if os.environ.get('DATABASE_URL'):
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL').replace('postgres://', 'postgresql://')
else:
    basedir = os.path.abspath(os.path.dirname(__file__))
    instance_path = os.path.join(basedir, 'instance')
    os.makedirs(instance_path, exist_ok=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "shop.db")}'

SECRET_KEY = os.environ.get('SECRET_KEY', '51870c0f00da27c6dd6d867835679acab0d9dfce4ec416976cb34e66fa438dae')
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
        def exempt(self, func):
            return func
    limiter = DummyLimiter()

# === MODELS ===
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    products = db.relationship('Product', backref='category', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    sku = db.Column(db.String(100), nullable=True, index=True)
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
    color = db.Column(db.String(100), default='')
    material = db.Column(db.String(200), default='')
    country = db.Column(db.String(100), default='')
    slug = db.Column(db.String(300), unique=True, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def generate_slug(self):
        """Generate URL slug from product name using Ukrainian transliteration."""
        base_slug = transliterate_to_slug(self.name)
        if not base_slug:
            base_slug = f'product-{self.id}'
        return base_slug

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

class NotificationSubscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    size = db.Column(db.String(20), nullable=False)
    contact_type = db.Column(db.String(10), nullable=False)  # 'email' or 'phone'
    contact_value = db.Column(db.String(200), nullable=False)
    notified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
_slugs_generated = False

@app.before_request
def _run_fix_once():
    global _shoe_sizes_fixed, _slugs_generated
    if not _shoe_sizes_fixed:
        _shoe_sizes_fixed = True
        fix_shoe_sizes()
        # Auto-add new columns if they don't exist (safe migration)
        try:
            from sqlalchemy import text
            for col_name, col_type in [('sku', 'VARCHAR(100)'), ('color', 'VARCHAR(100)'), ('material', 'VARCHAR(200)'), ('country', 'VARCHAR(100)')]:
                try:
                    db.session.execute(text(f"SELECT {col_name} FROM product LIMIT 1"))
                    db.session.rollback()
                except Exception:
                    db.session.rollback()
                    try:
                        db.session.execute(text(f"ALTER TABLE product ADD COLUMN {col_name} {col_type} DEFAULT ''"))
                        db.session.commit()
                        print(f"  Added column: {col_name}")
                    except Exception as e2:
                        db.session.rollback()
                        print(f"  Column {col_name} skip: {e2}")
        except Exception as e:
            db.session.rollback()
            print(f"Migration check: {e}")
    if not _slugs_generated:
        _slugs_generated = True
        try:
            # Check if slug column exists first
            from sqlalchemy import text
            try:
                db.session.execute(text("SELECT slug FROM product LIMIT 1"))
                db.session.rollback()  # Clean up the test query
            except Exception:
                db.session.rollback()
                print("Slug column not ready yet, skipping slug generation")
                return
            
            products_without_slug = Product.query.filter(
                (Product.slug == None) | (Product.slug == '')
            ).all()
            for prod in products_without_slug:
                base_slug = prod.generate_slug()
                slug = base_slug
                # Handle duplicates by appending -id
                existing = Product.query.filter(Product.slug == slug, Product.id != prod.id).first()
                if existing:
                    slug = f'{base_slug}-{prod.id}'
                prod.slug = slug
            if products_without_slug:
                db.session.commit()
                print(f"✅ Generated slugs for {len(products_without_slug)} products")
        except Exception as e:
            print(f"Error generating slugs: {e}")
            db.session.rollback()

# Security headers
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # Cache-Control for static assets
    if request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=2592000'  # 30 days
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

# === CONTEXT PROCESSOR ===
@app.context_processor
def inject_manager_status():
    """Inject manager_online status into all templates."""
    return {
        'manager_online': os.environ.get('MANAGER_ONLINE', 'false').lower() == 'true'
    }

# === BRANDS LIST ===
BRANDS_LIST = [
    {"name": "Massimo Dutti", "slug": "massimo-dutti"},
    {"name": "Calvin Klein", "slug": "calvin-klein"},
    {"name": "Tommy Hilfiger", "slug": "tommy-hilfiger"},
    {"name": "Polo Ralph Lauren", "slug": "polo-ralph-lauren"},
    {"name": "Karl Lagerfeld", "slug": "karl-lagerfeld"},
    {"name": "Premiata", "slug": "premiata"},
    {"name": "Armani Exchange", "slug": "armani-exchange"},
    {"name": "Boss", "slug": "boss"},
    {"name": "Levi's", "slug": "levis"},
    {"name": "Diesel", "slug": "diesel"},
    {"name": "Lacoste", "slug": "lacoste"},
    {"name": "Mango", "slug": "mango"},
    {"name": "Victoria's Secret", "slug": "victorias-secret"},
    {"name": "Michael Kors", "slug": "michael-kors"},
]

# === TEAM MEMBERS ===
DEFAULT_TEAM = [
    {"name": "Марк", "role": "Засновник", "photo": ""},
    {"name": "Анна", "role": "Менеджер", "photo": ""},
]

def get_team_members():
    """Get team members from env var or use default."""
    raw = os.environ.get('TEAM_MEMBERS')
    if raw:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass
    return DEFAULT_TEAM

# === SEO META DESCRIPTIONS ===
def get_catalog_meta_description(gender):
    """Generate unique meta description for catalog pages.

    Returns a string ≤160 chars containing store name,
    gender-specific keywords, brand names, and CTA.
    """
    if gender == 'men':
        return "Чоловічий одяг від Calvin Klein, Tommy Hilfiger, Boss, Massimo Dutti. Clever Shop — 100% оригінал з Європи. Доставка 1-2 дні. Замовляйте зараз!"
    elif gender == 'women':
        return "Жіночий одяг від Calvin Klein, Mango, Michael Kors, Victoria's Secret. Clever Shop — оригінал з Європи та США. Доставка 1-2 дні. Замовляйте!"
    else:
        return "Оригінальний брендовий одяг для чоловіків та жінок. Clever Shop — Calvin Klein, Tommy Hilfiger, Boss та інші. Доставка по Україні 1-2 дні."

# === ROUTES ===
@app.route('/')
def index():
    categories = Category.query.all()
    
    # Параметри фільтрації
    gender = request.args.get('gender', '')  # men / women
    page = request.args.get('page', 1, type=int)
    per_page = 24
    
    query = Product.query
    if gender == 'men':
        query = query.filter(Product.gender.in_(['чоловічий', 'унісекс']))
    elif gender == 'women':
        query = query.filter(Product.gender.in_(['жіночий', 'унісекс']))
    
    total = query.count()
    products = query.order_by(Product.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('index.html',
        categories=categories,
        products=products,
        page=page,
        total_pages=total_pages,
        total=total,
        gender=gender,
        per_page=per_page,
        catalog_meta=get_catalog_meta_description(gender),
        hero_video_url=os.environ.get('HERO_VIDEO_URL'),
        brands_list=BRANDS_LIST
    )

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
    return render_template('about.html', team_members=get_team_members())

@app.route('/contacts')
def contacts():
    return render_template('contacts.html')

@app.route('/product/<path:slug_or_id>')
def product(slug_or_id):
    # Check if it's a numeric ID
    try:
        product_id = int(slug_or_id)
        prod = Product.query.get_or_404(product_id)
        # If product has a slug, redirect 301 to slug URL
        if prod.slug:
            return redirect(url_for('product', slug_or_id=prod.slug), code=301)
        # No slug, render directly
        products = Product.query.limit(8).all()
        categories = Category.query.all()
        # Query review stats for Schema.org
        from sqlalchemy import func as sa_func
        review_stats = db.session.query(
            sa_func.count(Review.id),
            sa_func.avg(Review.rating)
        ).filter(Review.product_id == prod.id).first()
        review_count = review_stats[0] or 0
        avg_rating = float(review_stats[1]) if review_stats[1] else 0
        return render_template('product.html', product=prod, categories=categories, products=products,
                               review_count=review_count, avg_rating=avg_rating)
    except (ValueError, TypeError):
        pass
    # It's a slug - find product by slug
    prod = Product.query.filter_by(slug=slug_or_id).first_or_404()
    products = Product.query.limit(8).all()
    categories = Category.query.all()
    # Query review stats for Schema.org
    from sqlalchemy import func as sa_func
    review_stats = db.session.query(
        sa_func.count(Review.id),
        sa_func.avg(Review.rating)
    ).filter(Review.product_id == prod.id).first()
    review_count = review_stats[0] or 0
    avg_rating = float(review_stats[1]) if review_stats[1] else 0
    return render_template('product.html', product=prod, categories=categories, products=products,
                           review_count=review_count, avg_rating=avg_rating)

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

@app.route('/api/quick-order', methods=['POST'])
@limiter.limit("10 per minute")
@csrf.exempt
def quick_order():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Невірний формат запиту'}), 400

    name = (data.get('name') or '').strip()
    phone = (data.get('phone') or '').strip()
    product_id = data.get('product_id')
    size = data.get('size', '')

    # Validate name
    if not name:
        return jsonify({'error': "Ім'я обов'язкове"}), 400

    # Validate phone: +380 followed by 9 digits
    if not re.match(r'^\+380\d{9}$', phone):
        return jsonify({'error': 'Невірний формат телефону. Використовуйте +380XXXXXXXXX'}), 400

    # Validate product
    prod = Product.query.get(product_id)
    if not prod:
        return jsonify({'error': 'Товар не знайдено'}), 404

    # Create order
    items_data = json.dumps([{
        'id': prod.id,
        'name': prod.name,
        'price': prod.price,
        'quantity': 1,
        'size': size
    }])

    order = Order(
        customer_name=name,
        customer_phone=phone,
        customer_email='',
        delivery='Швидке замовлення - уточнити',
        items=items_data,
        total_price=prod.price,
        status='нове'
    )
    db.session.add(order)
    db.session.commit()

    # Send Telegram notification
    try:
        _notify_telegram(
            order.id, name, phone, prod.price,
            [{'name': prod.name, 'quantity': 1, 'price': prod.price, 'size': size}],
            'Швидке замовлення - уточнити',
            'очікується'
        )
    except Exception:
        pass

    return jsonify({'success': True, 'order_id': order.id})

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
@csrf.exempt
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
@csrf.exempt
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
@csrf.exempt
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
@app.route('/admin/login', methods=['GET', 'POST'])
@csrf.exempt
def admin_login_page():
    if request.method == 'POST':
        password = request.form.get('password')
        ADMIN_PASSWORD_HASH = os.environ.get('ADMIN_PASSWORD_HASH')
        # Перевіряємо і хеш і прямий пароль
        auth_ok = False
        if ADMIN_PASSWORD_HASH:
            try:
                auth_ok = check_password_hash(ADMIN_PASSWORD_HASH, password)
            except Exception:
                pass
        if not auth_ok:
            auth_ok = (password == 'clever.admin.123')
        if auth_ok:
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        return render_template('admin_login.html', error='Невірний пароль')
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
@csrf.exempt
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
@csrf.exempt
def api_products():
    if request.method == 'POST':
        if not session.get('admin'):
            return jsonify({'error': 'Unauthorized'}), 401
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Невірний формат запиту'}), 400
            image_urls = data.get('image_urls', [])
            # Handle case where image_urls is a string (from FormData hidden input)
            if isinstance(image_urls, str):
                try:
                    image_urls = json.loads(image_urls) if image_urls else []
                except (json.JSONDecodeError, TypeError):
                    image_urls = []
            main_image = image_urls[0] if image_urls else data.get('image_url', '')
            extra_images = ','.join(image_urls[1:]) if len(image_urls) > 1 else ''
            product = Product(
                name=data.get('name', '').strip(),
                description=data.get('description', ''),
                price=float(data.get('price', 0)),
                category_id=int(data.get('category_id', 1)),
                image_url=main_image,
                images=extra_images,
                stock=data.get('stock', 0),
                brand=data.get('brand', 'Clever'),
                sizes=data.get('sizes', 'XS,S,M,L,XL,XXL'),
                gender=data.get('gender', 'унісекс'),
                type=data.get('type', 'інше')
            )
            db.session.add(product)
            db.session.flush()  # Get the ID before commit
            
            # Generate slug
            try:
                base_slug = product.generate_slug()
                slug = base_slug
                existing = Product.query.filter(Product.slug == slug, Product.id != product.id).first()
                if existing:
                    slug = f'{base_slug}-{product.id}'
                product.slug = slug
            except Exception:
                product.slug = f'product-{product.id}'
            
            db.session.commit()
            return jsonify({'id': product.id})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
    return jsonify([{'id': p.id, 'name': p.name, 'price': p.price, 'image_url': p.image_url or '', 'brand': p.brand} for p in Product.query.all()])

@app.route('/api/products/<int:product_id>', methods=['PUT', 'DELETE'])
@csrf.exempt
def api_product(product_id):
    product = Product.query.get_or_404(product_id)
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    if request.method == 'PUT':
        data = request.get_json()
        product.name = data.get('name', product.name)
        product.description = data.get('description', product.description)
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
            continue
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
@csrf.exempt
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
    
    # Migrate: add slug column if it doesn't exist (PostgreSQL)
    try:
        from sqlalchemy import text, inspect
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('product')]
        if 'slug' not in columns:
            db.session.execute(text('ALTER TABLE product ADD COLUMN slug VARCHAR(300)'))
            db.session.commit()
            print("✅ Added 'slug' column to product table")
        # Create index if not exists
        try:
            db.session.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS ix_product_slug ON product (slug) WHERE slug IS NOT NULL'))
            db.session.commit()
        except Exception:
            db.session.rollback()
    except Exception as e:
        db.session.rollback()
        print(f"Migration check: {e}")
    
    # Migrate: create notification_subscriber table if it doesn't exist (PostgreSQL)
    try:
        from sqlalchemy import text as sa_text, inspect as sa_inspect
        insp = sa_inspect(db.engine)
        if 'notification_subscriber' not in insp.get_table_names():
            db.session.execute(sa_text('''
                CREATE TABLE IF NOT EXISTS notification_subscriber (
                    id SERIAL PRIMARY KEY,
                    product_id INTEGER NOT NULL REFERENCES product(id),
                    size VARCHAR(20) NOT NULL,
                    contact_type VARCHAR(10) NOT NULL,
                    contact_value VARCHAR(200) NOT NULL,
                    notified BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            '''))
            db.session.commit()
            print("✅ Created 'notification_subscriber' table")
    except Exception as e:
        db.session.rollback()
        print(f"NotificationSubscriber migration check: {e}")
    
    # Ensure all default categories exist
    default_categories = ['Одяг', 'Взуття', 'Аксесуари']
    existing = [c.name for c in Category.query.all()]
    for cat_name in default_categories:
        if cat_name not in existing:
            db.session.add(Category(name=cat_name))
    db.session.commit()

# === PRODUCT IMPORT ===
from product_import import generate_import_template, parse_import_file, execute_import

@app.route('/api/import/template')
def import_template():
    """Download Excel import template with validation."""
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    categories = [c.name for c in Category.query.all()]
    template_bytes = generate_import_template(categories)
    return app.response_class(
        template_bytes,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename=clever_import_template.xlsx'}
    )

@app.route('/api/import/preview', methods=['POST'])
@csrf.exempt
def import_preview():
    """Parse uploaded file and return preview JSON."""
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не обрано'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Файл не обрано'}), 400

    result = parse_import_file(file, file.filename)
    # Return first 50 rows for preview, plus stats
    preview_rows = result['rows'][:50]
    return jsonify({
        'rows': preview_rows,
        'total': result['total'],
        'preview_count': len(preview_rows),
        'errors': result['errors'],
    })

@app.route('/api/import/execute', methods=['POST'])
@csrf.exempt
def import_execute():
    """Execute the import from uploaded file."""
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не обрано'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Файл не обрано'}), 400

    # Parse
    result = parse_import_file(file, file.filename)
    if not result['rows']:
        return jsonify({
            'success': False,
            'report': {'created': 0, 'updated': 0, 'errors': 1, 'skipped': 0,
                       'details': [{'row': '-', 'name': '-', 'action': 'error',
                                    'message': 'Файл порожній або невірний формат'}]},
            'parse_errors': result['errors']
        })

    # Execute import
    # image_resolver=None for now — can be replaced with API-based resolver in future
    report = execute_import(
        rows=result['rows'],
        db_session=db.session,
        product_model=Product,
        category_model=Category,
        image_resolver=None,
        slug_generator=transliterate_to_slug
    )

    return jsonify({
        'success': True,
        'report': report,
        'parse_errors': result['errors']
    })

@app.route('/api/import/photo-search', methods=['POST'])
@csrf.exempt
def import_photo_search():
    """Generate photo search URLs for products without images."""
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    from product_import import generate_photo_search_query, get_products_without_photos

    data = request.get_json() or {}
    product_id = data.get('product_id')

    if product_id:
        # Single product
        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': 'Товар не знайдено'}), 404
        query = generate_photo_search_query(product)
        return jsonify({
            'product_id': product.id,
            'query': query,
            'search_url': f'https://www.google.com/search?q={query.replace(" ", "+")}&tbm=isch',
        })
    else:
        # All products without photos
        products = get_products_without_photos(Product)
        results = []
        for p in products[:100]:  # Limit to 100 at a time
            query = generate_photo_search_query(p)
            results.append({
                'product_id': p.id,
                'name': p.name,
                'sku': p.sku or '',
                'query': query,
                'search_url': f'https://www.google.com/search?q={query.replace(" ", "+")}&tbm=isch',
            })
        return jsonify({
            'total_without_photos': len(products),
            'results': results,
        })

@app.route('/api/import/update-photo', methods=['POST'])
@csrf.exempt
def import_update_photo():
    """Set photo URL for a product (after admin finds it)."""
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    product_id = data.get('product_id')
    image_url = data.get('image_url', '').strip()
    if not product_id or not image_url:
        return jsonify({'error': 'product_id та image_url обов\'язкові'}), 400
    product = Product.query.get(product_id)
    if not product:
        return jsonify({'error': 'Товар не знайдено'}), 404
    product.image_url = image_url
    db.session.commit()
    return jsonify({'success': True, 'product_id': product_id})

# === HEALTH CHECK ===
@app.route('/api/health')
@limiter.exempt
def health_check():
    """Health check endpoint for monitoring."""
    try:
        from sqlalchemy import text as sa_text
        product_count = db.session.execute(
            sa_text("SELECT COUNT(*) FROM product")
        ).scalar()
        order_count = db.session.execute(
            sa_text('SELECT COUNT(*) FROM "order"')
        ).scalar()
        return jsonify({
            "status": "ok",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "product_count": product_count,
            "order_count": order_count
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }), 503

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

# === NOTIFICATION SUBSCRIPTION ===
@app.route('/api/notify', methods=['POST'])
@csrf.exempt
@limiter.limit("10 per minute")
def subscribe_notification():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Невірний формат запиту'}), 400

    product_id = data.get('product_id')
    size = (data.get('size') or '').strip()
    contact = (data.get('contact') or '').strip()

    # Validate contact (email or phone)
    contact_type = None
    if re.match(r'^[^@]+@[^@]+\.[^@]+$', contact):
        contact_type = 'email'
    elif re.match(r'^\+380\d{9}$', contact):
        contact_type = 'phone'
    else:
        return jsonify({'error': 'Невірний формат email або телефону'}), 400

    # Validate product exists
    product = Product.query.get(product_id)
    if not product:
        return jsonify({'error': 'Товар не знайдено'}), 404

    subscriber = NotificationSubscriber(
        product_id=product_id,
        size=size,
        contact_type=contact_type,
        contact_value=contact
    )
    db.session.add(subscriber)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Ми повідомимо вас, коли цей розмір з\'явиться'})

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

@app.route('/api/categories', methods=['POST'])
@csrf.exempt
def api_categories_create():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Назва обов\'язкова'}), 400
    if Category.query.filter_by(name=name).first():
        return jsonify({'error': 'Категорія вже існує'}), 400
    cat = Category(name=name)
    db.session.add(cat)
    db.session.commit()
    return jsonify({'id': cat.id, 'name': cat.name})

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
            'loc': url_for('product', slug_or_id=product.slug or str(product.id), _external=True),
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
