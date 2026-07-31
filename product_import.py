"""
Product Import Module for Clever Shop Admin Panel.
Handles Excel (.xlsx) and CSV import with preview, create/update, and reporting.

Architecture note: Image resolution is handled via `image_resolver` parameter,
making it easy to plug in automated image search in the future without changing
the import logic.
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
    {'key': 'name', 'label': 'Назва товару *', 'required': True, 'example': 'Куртка Tommy Hilfiger'},
    {'key': 'brand', 'label': 'Бренд', 'required': False, 'example': 'Tommy Hilfiger'},
    {'key': 'price', 'label': 'Ціна (грн) *', 'required': True, 'example': '4500'},
    {'key': 'category', 'label': 'Категорія', 'required': False, 'example': 'Верхній одяг'},
    {'key': 'gender', 'label': 'Стать', 'required': False, 'example': 'чоловічий'},
    {'key': 'type', 'label': 'Тип одягу', 'required': False, 'example': 'куртка'},
    {'key': 'sizes', 'label': 'Розміри', 'required': False, 'example': 'S,M,L,XL'},
    {'key': 'stock', 'label': 'Кількість', 'required': False, 'example': '5'},
    {'key': 'description', 'label': 'Опис', 'required': False, 'example': 'Оригінальна куртка з Європи'},
    {'key': 'image_url', 'label': 'Фото URL', 'required': False, 'example': 'https://example.com/photo.jpg'},
]

VALID_GENDERS = ['чоловічий', 'жіночий', 'унісекс']
VALID_TYPES = ['футболка', 'поло', 'сорочка', 'джинси', 'куртка', 'светр', 'штани', 'кросівки', 'сукня', 'аксесуари', 'білизна', 'інше']
VALID_BRANDS = [
    'Massimo Dutti', 'Calvin Klein', 'Tommy Hilfiger', 'Polo Ralph Lauren',
    'Karl Lagerfeld', 'Premiata', 'Armani Exchange', 'Boss', "Levi's",
    'Diesel', 'Lacoste', 'Mango', "Victoria's Secret", 'Michael Kors'
]


# ============================================================
# TEMPLATE GENERATION
# ============================================================

def generate_import_template(categories: List[str]) -> bytes:
    """Generate an Excel template with headers, example row, and data validation."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Товари"

    # Styles
    header_font = Font(bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="10B981", end_color="10B981", fill_type="solid")
    example_fill = PatternFill(start_color="F0FDF4", end_color="F0FDF4", fill_type="solid")
    thin_border = Border(
        left=Side(style='thin', color='D1D5DB'),
        right=Side(style='thin', color='D1D5DB'),
        top=Side(style='thin', color='D1D5DB'),
        bottom=Side(style='thin', color='D1D5DB')
    )

    # Write headers
    for col_idx, col in enumerate(IMPORT_COLUMNS, 1):
        cell = ws.cell(row=1, column=col_idx, value=col['label'])
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = thin_border
        ws.column_dimensions[get_column_letter(col_idx)].width = max(len(col['label']), len(col['example'])) + 4

    # Write example row
    for col_idx, col in enumerate(IMPORT_COLUMNS, 1):
        cell = ws.cell(row=2, column=col_idx, value=col['example'])
        cell.fill = example_fill
        cell.border = thin_border
        cell.font = Font(italic=True, color="6B7280")

    # Data validation for Gender (column 5)
    gender_dv = DataValidation(type="list", formula1='"' + ','.join(VALID_GENDERS) + '"', allow_blank=True)
    gender_dv.error = "Оберіть: чоловічий, жіночий або унісекс"
    gender_dv.errorTitle = "Невірна стать"
    ws.add_data_validation(gender_dv)
    gender_dv.add(f'E3:E1000')

    # Data validation for Type (column 6)
    type_dv = DataValidation(type="list", formula1='"' + ','.join(VALID_TYPES) + '"', allow_blank=True)
    type_dv.error = "Оберіть тип зі списку"
    type_dv.errorTitle = "Невірний тип"
    ws.add_data_validation(type_dv)
    type_dv.add(f'F3:F1000')

    # Data validation for Category (column 4)
    if categories:
        cat_dv = DataValidation(type="list", formula1='"' + ','.join(categories) + '"', allow_blank=True)
        cat_dv.error = "Оберіть категорію зі списку"
        ws.add_data_validation(cat_dv)
        cat_dv.add(f'D3:D1000')

    # Data validation for Brand (column 2)
    brand_dv = DataValidation(type="list", formula1='"' + ','.join(VALID_BRANDS) + '"', allow_blank=True)
    ws.add_data_validation(brand_dv)
    brand_dv.add(f'B3:B1000')

    # Instructions sheet
    ws_help = wb.create_sheet("Інструкція")
    instructions = [
        ("Як заповнювати шаблон:", ""),
        ("", ""),
        ("1. Назва товару", "Обов'язкове поле. Якщо товар з такою назвою вже існує — він буде оновлений."),
        ("2. Бренд", "Оберіть зі списку або введіть свій."),
        ("3. Ціна", "Обов'язкове поле. Число в гривнях (без 'грн')."),
        ("4. Категорія", "Оберіть зі списку. Якщо пусто — буде 'Верхній одяг'."),
        ("5. Стать", "чоловічий / жіночий / унісекс"),
        ("6. Тип одягу", "Оберіть зі списку."),
        ("7. Розміри", "Через кому: XS,S,M,L,XL або з наявністю: XS:1,S:1,M:0,L:1"),
        ("8. Кількість", "Загальна кількість на складі (число)."),
        ("9. Опис", "Текст опису товару."),
        ("10. Фото URL", "Пряме посилання на фото. Можна кілька через кому."),
        ("", ""),
        ("⚠️ Важливо:", ""),
        ("", "Перший рядок (зелений) — заголовки. НЕ видаляйте!"),
        ("", "Другий рядок (світло-зелений) — приклад. Можете видалити або замінити."),
        ("", "Якщо товар з такою самою НАЗВОЮ вже є в магазині — він ОНОВИТЬСЯ."),
        ("", "Нові товари будуть СТВОРЕНІ автоматично."),
    ]
    for row_idx, (col_a, col_b) in enumerate(instructions, 1):
        ws_help.cell(row=row_idx, column=1, value=col_a).font = Font(bold=True if col_a and not col_a.startswith(' ') else False)
        ws_help.cell(row=row_idx, column=2, value=col_b)
    ws_help.column_dimensions['A'].width = 25
    ws_help.column_dimensions['B'].width = 70

    # Save to bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


# ============================================================
# FILE PARSING
# ============================================================

def parse_import_file(file_storage, filename: str) -> Dict[str, Any]:
    """
    Parse uploaded Excel or CSV file into a list of row dicts.
    Returns: {'rows': [...], 'total': int, 'errors': [...]}
    """
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    if ext == 'xlsx':
        return _parse_xlsx(file_storage)
    elif ext == 'csv':
        return _parse_csv(file_storage)
    else:
        return {'rows': [], 'total': 0, 'errors': [f'Непідтримуваний формат: .{ext}. Використовуйте .xlsx або .csv']}


def _parse_xlsx(file_storage) -> Dict[str, Any]:
    """Parse .xlsx file."""
    try:
        wb = load_workbook(file_storage, read_only=True, data_only=True)
        ws = wb.active
        rows = []
        errors = []

        # Read header row to map columns
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
        return {'rows': [], 'total': 0, 'errors': [f'Помилка читання файлу: {str(e)}']}


def _parse_csv(file_storage) -> Dict[str, Any]:
    """Parse .csv file (UTF-8 or CP1251)."""
    try:
        raw = file_storage.read()
        # Try UTF-8 first, then CP1251 (common for Ukrainian Excel exports)
        for encoding in ['utf-8-sig', 'utf-8', 'cp1251']:
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            return {'rows': [], 'total': 0, 'errors': ['Не вдалося визначити кодування файлу']}

        # Detect delimiter
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
            # Pad row to match header length
            while len(row) < len(header_row):
                row.append('')
            parsed = _parse_row(row, col_map, row_idx, errors)
            if parsed:
                rows.append(parsed)

        return {'rows': rows, 'total': len(rows), 'errors': errors}
    except Exception as e:
        return {'rows': [], 'total': 0, 'errors': [f'Помилка читання CSV: {str(e)}']}


def _map_columns(header_row: List[str]) -> Dict[str, int]:
    """Map header names to column indices using fuzzy matching."""
    col_map = {}
    keyword_map = {
        'name': ['назва', 'name', 'найменування', 'товар', 'назва товару'],
        'brand': ['бренд', 'brand', 'виробник', 'марка'],
        'price': ['ціна', 'price', 'вартість', 'прайс'],
        'category': ['категорія', 'category', 'розділ', 'група'],
        'gender': ['стать', 'gender', 'пол', 'для кого'],
        'type': ['тип', 'type', 'вид', 'тип одягу'],
        'sizes': ['розмір', 'sizes', 'size', 'розміри'],
        'stock': ['кількість', 'stock', 'залишок', 'наявність', 'qty'],
        'description': ['опис', 'description', 'desc', 'характеристика'],
        'image_url': ['фото', 'image', 'photo', 'url', 'зображення', 'фото url'],
    }

    for col_idx, header in enumerate(header_row):
        header_clean = header.replace('*', '').replace('(грн)', '').strip()
        for field_key, keywords in keyword_map.items():
            if field_key not in col_map:
                for kw in keywords:
                    if kw in header_clean:
                        col_map[field_key] = col_idx
                        break

    return col_map


def _parse_row(row, col_map: Dict[str, int], row_idx: int, errors: List[str]) -> Optional[Dict[str, Any]]:
    """Parse a single row using the column mapping."""
    def get_val(key: str, default='') -> str:
        idx = col_map.get(key)
        if idx is None or idx >= len(row):
            return default
        val = row[idx]
        return str(val).strip() if val is not None else default

    name = get_val('name')
    price_str = get_val('price')

    # Validate required fields
    if not name:
        errors.append(f'Рядок {row_idx}: пуста назва — пропущено')
        return None

    # Parse price
    price = 0.0
    if price_str:
        try:
            # Handle various formats: "4 500", "4500.00", "4,500"
            cleaned = price_str.replace(' ', '').replace(',', '.').replace('грн', '').replace('₴', '').strip()
            price = float(cleaned)
        except (ValueError, TypeError):
            errors.append(f'Рядок {row_idx} ({name}): невірна ціна "{price_str}" — встановлено 0')
            price = 0.0

    if price <= 0:
        errors.append(f'Рядок {row_idx} ({name}): ціна = 0 або відсутня')

    # Parse stock
    stock = 0
    stock_str = get_val('stock', '0')
    try:
        stock = int(float(stock_str)) if stock_str else 0
    except (ValueError, TypeError):
        stock = 0

    # Normalize gender
    gender = get_val('gender', 'унісекс').lower()
    if gender not in VALID_GENDERS:
        if 'чол' in gender or 'men' in gender.lower() or 'man' in gender.lower():
            gender = 'чоловічий'
        elif 'жін' in gender or 'women' in gender.lower() or 'woman' in gender.lower():
            gender = 'жіночий'
        else:
            gender = 'унісекс'

    # Normalize type
    product_type = get_val('type', 'інше').lower()
    if product_type not in VALID_TYPES:
        product_type = 'інше'

    return {
        'name': name,
        'brand': get_val('brand', 'Clever'),
        'price': price,
        'category': get_val('category', ''),
        'gender': gender,
        'type': product_type,
        'sizes': get_val('sizes', 'XS,S,M,L,XL,XXL'),
        'stock': stock,
        'description': get_val('description', ''),
        'image_url': get_val('image_url', ''),
        'row_num': row_idx,
    }


# ============================================================
# IMPORT EXECUTION
# ============================================================

def execute_import(
    rows: List[Dict[str, Any]],
    db_session,
    product_model,
    category_model,
    image_resolver: Optional[Callable[[str], str]] = None,
    slug_generator: Optional[Callable[[str], str]] = None
) -> Dict[str, Any]:
    """
    Execute the import: create new products or update existing ones.

    Args:
        rows: Parsed row dicts from parse_import_file
        db_session: SQLAlchemy session
        product_model: Product class
        category_model: Category class
        image_resolver: Optional callable(url) -> local_url (for future image API integration)
        slug_generator: Optional callable(name) -> slug

    Returns: Report dict with created, updated, errors, details
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

    for row in rows:
        try:
            # Find or resolve category
            cat_name = row.get('category', '').strip()
            category_id = default_category_id
            if cat_name:
                category_id = categories.get(cat_name.lower(), default_category_id)

            # Resolve image URL (hook for future automation)
            image_url = row.get('image_url', '')
            if image_url and image_resolver:
                try:
                    image_url = image_resolver(image_url)
                except Exception:
                    pass  # Keep original URL on error

            # Check if product exists (by exact name match)
            existing = product_model.query.filter(
                product_model.name == row['name']
            ).first()

            if existing:
                # UPDATE existing product
                existing.price = row['price'] if row['price'] > 0 else existing.price
                existing.brand = row['brand'] or existing.brand
                existing.category_id = category_id
                existing.gender = row['gender']
                existing.type = row['type']
                existing.sizes = row['sizes'] or existing.sizes
                existing.stock = row['stock'] if row['stock'] > 0 else existing.stock
                if row['description']:
                    existing.description = row['description']
                if image_url:
                    existing.image_url = image_url
                report['updated'] += 1
                report['details'].append({
                    'row': row.get('row_num', '?'),
                    'name': row['name'],
                    'action': 'updated',
                    'message': f'Оновлено: ціна={existing.price}, stock={existing.stock}'
                })
            else:
                # CREATE new product
                new_product = product_model(
                    name=row['name'],
                    brand=row['brand'] or 'Clever',
                    price=row['price'],
                    category_id=category_id,
                    gender=row['gender'],
                    type=row['type'],
                    sizes=row['sizes'] or 'XS,S,M,L,XL,XXL',
                    stock=row['stock'],
                    description=row['description'],
                    image_url=image_url,
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
                    'message': f'Створено: ID={new_product.id}'
                })

        except Exception as e:
            report['errors'] += 1
            report['details'].append({
                'row': row.get('row_num', '?'),
                'name': row.get('name', '?'),
                'action': 'error',
                'message': str(e)
            })

    # Commit all changes
    try:
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        report['errors'] = len(rows)
        report['created'] = 0
        report['updated'] = 0
        report['details'] = [{'row': '-', 'name': '-', 'action': 'error', 'message': f'Помилка збереження: {str(e)}'}]

    return report
