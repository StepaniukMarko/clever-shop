"""
Product Import Module for Clever Shop Admin Panel v2.
Handles Excel (.xlsx) and CSV import with:
- Flexible column mapping (fuzzy match)
- SKU-based upsert (update existing, create new)
- Batch processing for 500-2000+ products
- Photo search query generation
- Caching of photo search results
"""

import csv
import io
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation


# ============================================================
# CONSTANTS
# ============================================================

IMPORT_COLUMNS = [
    {'key': 'brand', 'label': 'Бренд', 'required': False, 'example': 'Massimo Dutti'},
    {'key': 'name', 'label': 'Назва товару *', 'required': True, 'example': 'Braided leather belt'},
    {'key': 'sku', 'label': 'Артикул (SKU)', 'required': False, 'example': '1004/504/800'},
    {'key': 'material', 'label': 'Матеріал', 'required': False, 'example': 'Натуральна шкіра'},
    {'key': 'country', 'label': 'Країна', 'required': False, 'example': 'Іспанія'},
    {'key': 'category', 'label': 'Категорія', 'required': False, 'example': 'Аксесуари'},
    {'key': 'color', 'label': 'Колір', 'required': False, 'example': 'Чорний'},
    {'key': 'sizes', 'label': 'Розмір', 'required': False, 'example': 'M,L,XL'},
    {'key': 'stock', 'label': 'Кількість', 'required': False, 'example': '5'},
    {'key': 'price', 'label': 'Ціна (грн) *', 'required': True, 'example': '3200'},
]

# Keyword mapping for fuzzy column detection
COLUMN_KEYWORDS = {
    'brand': ['бренд', 'brand', 'виробник', 'марка', 'торгова марка'],
    'name': ['назва', 'name', 'найменування', 'товар', 'назва товару', 'наименование'],
    'sku': ['артикул', 'sku', 'арт', 'код', 'модель', 'article', 'ref'],
    'material': ['матеріал', 'material', 'склад', 'тканина', 'состав'],
    'country': ['країна', 'country', 'виробництво', 'страна', 'origin'],
    'category': ['категорія', 'category', 'розділ', 'група', 'тип', 'group'],
    'color': ['колір', 'color', 'colour', 'цвет', 'кольор'],
    'sizes': ['розмір', 'sizes', 'size', 'розміри', 'размер'],
    'stock': ['кількість', 'stock', 'залишок', 'наявність', 'qty', 'количество', 'кол-во'],
    'price': ['ціна', 'price', 'вартість', 'прайс', 'цена', 'стоимость'],
}


# ============================================================
# TEMPLATE GENERATION
# ============================================================

def generate_import_template(categories: List[str]) -> bytes:
    """Generate Excel template with headers, example row, and data validation."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Товари"

    header_font = Font(bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
    example_fill = PatternFill(start_color="EFF6FF", end_color="EFF6FF", fill_type="solid")
    thin_border = Border(
        left=Side(style='thin', color='D1D5DB'),
        right=Side(style='thin', color='D1D5DB'),
        top=Side(style='thin', color='D1D5DB'),
        bottom=Side(style='thin', color='D1D5DB')
    )

    for col_idx, col in enumerate(IMPORT_COLUMNS, 1):
        cell = ws.cell(row=1, column=col_idx, value=col['label'])
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = thin_border
        ws.column_dimensions[get_column_letter(col_idx)].width = max(len(col['label']), len(col['example'])) + 4

    for col_idx, col in enumerate(IMPORT_COLUMNS, 1):
        cell = ws.cell(row=2, column=col_idx, value=col['example'])
        cell.fill = example_fill
        cell.border = thin_border
        cell.font = Font(italic=True, color="6B7280")

    # Instructions sheet
    ws_help = wb.create_sheet("Інструкція")
    instructions = [
        ("Як заповнювати:", ""),
        ("", ""),
        ("1. Бренд", "Назва бренду (Massimo Dutti, Calvin Klein тощо)"),
        ("2. Назва товару", "Обов'язкове. Назва товару"),
        ("3. Артикул (SKU)", "Унікальний код товару. Використовується для оновлення"),
        ("4. Матеріал", "Склад тканини або матеріал"),
        ("5. Країна", "Країна виробництва"),
        ("6. Категорія", "Група товару (Верхній одяг, Взуття тощо)"),
        ("7. Колір", "Колір товару"),
        ("8. Розмір", "Через кому: S,M,L,XL або 40,42,44"),
        ("9. Кількість", "Залишок на складі"),
        ("10. Ціна", "Ціна в гривнях (число)"),
        ("", ""),
        ("ВАЖЛИВО:", ""),
        ("", "Якщо товар з таким АРТИКУЛОМ вже є — він ОНОВИТЬСЯ"),
        ("", "Нові товари СТВОРЮЮТЬСЯ автоматично"),
        ("", "Перший рядок — заголовки. Другий — приклад (можна видалити)"),
    ]
    for row_idx, (a, b) in enumerate(instructions, 1):
        ws_help.cell(row=row_idx, column=1, value=a).font = Font(bold=bool(a))
        ws_help.cell(row=row_idx, column=2, value=b)
    ws_help.column_dimensions['A'].width = 22
    ws_help.column_dimensions['B'].width = 60

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


# ============================================================
# FILE PARSING
# ============================================================

def parse_import_file(file_storage, filename: str) -> Dict[str, Any]:
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext == 'xlsx':
        return _parse_xlsx(file_storage)
    elif ext == 'csv':
        return _parse_csv(file_storage)
    else:
        return {'rows': [], 'total': 0, 'errors': [f'Непідтримуваний формат: .{ext}']}


def _parse_xlsx(file_storage) -> Dict[str, Any]:
    try:
        wb = load_workbook(file_storage, read_only=True, data_only=True)
        ws = wb.active
        rows = []
        errors = []

        header_row = [str(cell.value or '').strip().lower() for cell in ws[1]]
        col_map = _map_columns(header_row)

        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not row or all(v is None or str(v).strip() == '' for v in row):
                continue
            parsed = _parse_row(row, col_map, row_idx, errors)
            if parsed:
                rows.append(parsed)

        wb.close()
        return {'rows': rows, 'total': len(rows), 'errors': errors}
    except Exception as e:
        return {'rows': [], 'total': 0, 'errors': [f'Помилка читання: {str(e)}']}


def _parse_csv(file_storage) -> Dict[str, Any]:
    try:
        raw = file_storage.read()
        for encoding in ['utf-8-sig', 'utf-8', 'cp1251', 'windows-1251']:
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            return {'rows': [], 'total': 0, 'errors': ['Не вдалося визначити кодування']}

        first_line = text.split('\n')[0]
        delimiter = ';' if ';' in first_line else ','

        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        header_row = [h.strip().lower() for h in next(reader)]
        col_map = _map_columns(header_row)

        rows = []
        errors = []
        for row_idx, row in enumerate(reader, start=2):
            if not row or all(v.strip() == '' for v in row):
                continue
            while len(row) < len(header_row):
                row.append('')
            parsed = _parse_row(row, col_map, row_idx, errors)
            if parsed:
                rows.append(parsed)

        return {'rows': rows, 'total': len(rows), 'errors': errors}
    except Exception as e:
        return {'rows': [], 'total': 0, 'errors': [f'Помилка CSV: {str(e)}']}


def _map_columns(header_row: List[str]) -> Dict[str, int]:
    """Map header names to column indices using fuzzy keyword matching."""
    col_map = {}
    for col_idx, header in enumerate(header_row):
        header_clean = header.replace('*', '').replace('(грн)', '').replace('(sku)', '').strip()
        for field_key, keywords in COLUMN_KEYWORDS.items():
            if field_key not in col_map:
                for kw in keywords:
                    if kw in header_clean:
                        col_map[field_key] = col_idx
                        break

    # Fallback: if columns are in exact A-J order without headers
    if not col_map or len(col_map) < 3:
        # Try positional mapping (A=brand, B=name, C=sku, D=material, E=country, F=category, G=color, H=sizes, I=stock, J=price)
        keys = ['brand', 'name', 'sku', 'material', 'country', 'category', 'color', 'sizes', 'stock', 'price']
        for i, key in enumerate(keys):
            if i < len(header_row):
                col_map[key] = i

    return col_map


def _parse_row(row, col_map: Dict[str, int], row_idx: int, errors: List[str]) -> Optional[Dict[str, Any]]:
    def get_val(key: str, default='') -> str:
        idx = col_map.get(key)
        if idx is None or idx >= len(row):
            return default
        val = row[idx]
        return str(val).strip() if val is not None else default

    name = get_val('name')
    price_str = get_val('price')

    if not name:
        return None  # Skip silently for empty rows

    # Parse price
    price = 0.0
    if price_str:
        try:
            cleaned = price_str.replace(' ', '').replace(',', '.').replace('грн', '').replace('₴', '').strip()
            price = float(cleaned)
        except (ValueError, TypeError):
            errors.append(f'Рядок {row_idx} ({name}): невірна ціна "{price_str}"')

    # Parse stock
    stock = 0
    stock_str = get_val('stock', '0')
    try:
        stock = int(float(stock_str)) if stock_str else 0
    except (ValueError, TypeError):
        stock = 0

    # Clean SKU (remove slashes for matching but keep original)
    sku = get_val('sku', '')

    return {
        'brand': get_val('brand', ''),
        'name': name,
        'sku': sku,
        'material': get_val('material', ''),
        'country': get_val('country', ''),
        'category': get_val('category', ''),
        'color': get_val('color', ''),
        'sizes': get_val('sizes', ''),
        'stock': stock,
        'price': price,
        'row_num': row_idx,
    }


# ============================================================
# NAME NORMALIZATION (supplier names → Ukrainian product names)
# ============================================================

def normalize_product_name(original_name: str, brand: str, category: str, material: str) -> str:
    """
    Convert raw supplier product names to clean Ukrainian names.
    
    Logic:
    1. Determine if material is leather → prefix "Шкіряний/Шкіряна"
    2. Map category to Ukrainian noun
    3. For shoes: detect type from original name
    4. Format: "{prefix} {category_ua} {brand}"
    """
    cat_lower = category.lower().strip()
    mat_lower = material.lower().strip()
    name_lower = original_name.lower().strip()
    
    # Check if leather material
    is_leather = any(kw in mat_lower for kw in ['натуральна шкіра', 'шкіра', 'nappa', 'napa', 'piel', 'leather', 'cuero', 'couro'])
    
    # Category mapping with gender (for prefix agreement)
    # Format: (base_name, is_feminine)
    CATEGORY_MAP = {
        'ремінь': ('ремінь', False),
        'гаманець': ('гаманець', False),
        'сумка': ('сумка', True),
        'рюкзак': ('рюкзак', False),
        'рукавиці': ('рукавиці', True),  # plural feminine
        'кардхолдер': ('кардхолдер', False),
    }
    
    # Check for shoe category
    if cat_lower == 'взуття' or 'взутт' in cat_lower:
        shoe_type = _detect_shoe_type(name_lower)
        if brand:
            return f'{shoe_type} {brand}'
        return shoe_type
    
    # Non-shoe categories
    cat_info = CATEGORY_MAP.get(cat_lower)
    if cat_info:
        base_name, is_feminine = cat_info
        if is_leather:
            prefix = 'Шкіряна' if is_feminine else 'Шкіряний'
            # Special case for plural
            if cat_lower == 'рукавиці':
                prefix = 'Шкіряні'
            result = f'{prefix} {base_name}'
        else:
            result = base_name.capitalize()
        
        if brand:
            result += f' {brand}'
        return result
    
    # Fallback: capitalize category + brand
    if category and brand:
        return f'{category} {brand}'
    elif brand:
        return f'{brand} {original_name[:50]}'
    
    return original_name[:100]


def _detect_shoe_type(name_lower: str) -> str:
    """Detect shoe type from original supplier name."""
    SHOE_KEYWORDS = {
        'Черевики': ['boot', 'bota', 'botin', 'botín', 'ankle'],
        'Кросівки': ['trainer', 'sneaker', 'deportiv', 'running', 'sport', 'zapatilla'],
        'Лофери': ['loafer', 'mocasín', 'mocasin'],
        'Мокасини': ['moccasin', 'mocassin', 'driving'],
        'Сандалі': ['sandal', 'sandalia'],
        'Туфлі': ['oxford', 'derby', 'zapato', 'shoe', 'sapato'],
        'Кеди': ['canvas', 'vulc', 'plimsoll'],
    }
    
    for ua_type, keywords in SHOE_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return ua_type
    
    return 'Взуття'  # default fallback


# ============================================================
# IMPORT EXECUTION (SKU-based upsert)
# ============================================================

def execute_import(
    rows: List[Dict[str, Any]],
    db_session,
    product_model,
    category_model,
    image_resolver: Optional[Callable[[str], str]] = None,
    slug_generator: Optional[Callable[[str], str]] = None,
    batch_size: int = 50
) -> Dict[str, Any]:
    """
    Execute import with SKU-based upsert logic.
    Processes in batches to avoid timeout on large catalogs.
    """
    report = {
        'created': 0,
        'updated': 0,
        'errors': 0,
        'skipped': 0,
        'details': [],
    }

    # Pre-load categories map
    categories = {c.name.lower(): c.id for c in category_model.query.all()}
    default_category_id = list(categories.values())[0] if categories else 1

    for batch_start in range(0, len(rows), batch_size):
        batch = rows[batch_start:batch_start + batch_size]

        for row in batch:
            try:
                cat_name = row.get('category', '').strip()
                category_id = default_category_id
                if cat_name:
                    category_id = categories.get(cat_name.lower(), default_category_id)

                # SKU-based lookup (primary), fallback to name
                existing = None
                sku = row.get('sku', '').strip()
                if sku:
                    existing = product_model.query.filter(product_model.sku == sku).first()
                if not existing and row['name']:
                    existing = product_model.query.filter(product_model.name == row['name']).first()

                if existing:
                    # UPDATE
                    if row['price'] > 0:
                        existing.price = row['price']
                    if row['stock'] > 0:
                        existing.stock = row['stock']
                    if row.get('brand'):
                        existing.brand = row['brand']
                    if row.get('material'):
                        existing.material = row['material']
                    if row.get('country'):
                        existing.country = row['country']
                    if row.get('color'):
                        existing.color = row['color']
                    if row.get('sizes'):
                        existing.sizes = row['sizes']
                    if row.get('sku') and not existing.sku:
                        existing.sku = row['sku']
                    existing.category_id = category_id

                    report['updated'] += 1
                    report['details'].append({
                        'row': row.get('row_num', '?'),
                        'name': row['name'],
                        'action': 'updated',
                        'message': f'SKU={sku or "N/A"}'
                    })
                else:
                    # CREATE
                    # Normalize name from supplier language to Ukrainian
                    original_name = row['name']
                    normalized_name = normalize_product_name(
                        original_name=original_name,
                        brand=row.get('brand', ''),
                        category=row.get('category', ''),
                        material=row.get('material', '')
                    )
                    
                    new_product = product_model(
                        name=normalized_name,
                        original_name=original_name,
                        sku=sku or None,
                        brand=row.get('brand', '') or 'Clever',
                        price=row['price'] if row['price'] > 0 else 0,
                        category_id=category_id,
                        color=row.get('color', ''),
                        material=row.get('material', ''),
                        country=row.get('country', ''),
                        sizes=row.get('sizes', ''),
                        stock=row['stock'],
                        description='',
                        image_url='',
                    )
                    db_session.add(new_product)
                    db_session.flush()

                    # Generate slug
                    if slug_generator:
                        try:
                            base_slug = slug_generator(new_product.name)
                            slug = base_slug
                            dup = product_model.query.filter(
                                product_model.slug == slug,
                                product_model.id != new_product.id
                            ).first()
                            if dup:
                                slug = f'{base_slug}-{new_product.id}'
                            new_product.slug = slug
                        except Exception:
                            new_product.slug = f'product-{new_product.id}'

                    report['created'] += 1
                    report['details'].append({
                        'row': row.get('row_num', '?'),
                        'name': row['name'],
                        'action': 'created',
                        'message': f'ID={new_product.id}'
                    })

            except Exception as e:
                report['errors'] += 1
                report['details'].append({
                    'row': row.get('row_num', '?'),
                    'name': row.get('name', '?'),
                    'action': 'error',
                    'message': str(e)
                })

        # Commit each batch
        try:
            db_session.commit()
        except Exception as e:
            db_session.rollback()
            report['errors'] += len(batch)
            report['details'].append({
                'row': '-', 'name': '-', 'action': 'error',
                'message': f'Batch commit error: {str(e)}'
            })

    return report


# ============================================================
# PHOTO SEARCH HELPERS
# ============================================================

def generate_photo_search_query(product) -> str:
    """Generate search query for finding product photos."""
    parts = []
    if product.brand:
        parts.append(product.brand)
    if product.sku:
        # Remove slashes for better search
        parts.append(product.sku.replace('/', ''))
    if product.name:
        parts.append(product.name)
    return ' '.join(parts).strip()


def get_products_without_photos(product_model) -> list:
    """Get all products that don't have images."""
    return product_model.query.filter(
        (product_model.image_url == None) | (product_model.image_url == '')
    ).all()
