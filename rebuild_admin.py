"""
Rebuilds admin_dashboard.html by removing all duplicate sections.
Keeps only the first occurrence of each modal/script.
"""
content = open('templates/admin_dashboard.html', encoding='utf-8').read()

# Find the first </html> and cut everything after it
first_html = content.find('</html>')
if first_html != -1:
    content = content[:first_html + len('</html>')]

# Now find the LAST </body> before </html> and insert edit modal before it
last_body = content.rfind('</body>')

# Check if edit-modal already exists
if 'id="edit-modal"' in content:
    # Remove existing edit-modal (it might be broken)
    start = content.find('\n<!-- Edit Product Modal -->')
    if start == -1:
        start = content.find('<div id="edit-modal"')
    end = content.find('</div>\n</body>')
    if start != -1 and end != -1:
        content = content[:start] + '\n</body>\n</html>'
    else:
        # Just ensure clean ending
        last_body = content.rfind('</body>')
        if last_body != -1:
            content = content[:last_body] + '</body>\n</html>'

# Remove duplicate editProduct/submitEditForm/closeEditModal functions
# Keep only the ones in the main script block
lines = content.split('\n')
clean_lines = []
skip_until = None
i = 0
while i < len(lines):
    line = lines[i]
    # Skip duplicate script blocks after </html>
    if skip_until and line.strip() != skip_until:
        i += 1
        continue
    elif skip_until and line.strip() == skip_until:
        skip_until = None
        i += 1
        continue
    clean_lines.append(line)
    i += 1

content = '\n'.join(clean_lines)

# Now add clean edit modal before </body>
edit_modal = '''
<!-- Edit Product Modal -->
<div id="edit-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:9999;align-items:center;justify-content:center;">
    <div style="background:white;border-radius:16px;padding:2rem;width:90%;max-width:520px;max-height:90vh;overflow-y:auto;box-shadow:0 25px 50px rgba(0,0,0,0.3);">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem;">
            <h3 style="margin:0;font-size:1.25rem;font-weight:700;">✏️ Редагувати товар</h3>
            <button onclick="closeEditModal()" style="background:none;border:none;font-size:1.75rem;cursor:pointer;color:#6B7280;line-height:1;">×</button>
        </div>
        <form onsubmit="submitEditForm(event)">
            <input type="hidden" id="edit-id">
            <div style="margin-bottom:1rem;">
                <label style="display:block;font-weight:600;margin-bottom:0.4rem;">Назва</label>
                <input type="text" id="edit-name" required style="width:100%;padding:0.75rem;border:2px solid #E5E7EB;border-radius:8px;font-size:0.95rem;box-sizing:border-box;">
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem;">
                <div>
                    <label style="display:block;font-weight:600;margin-bottom:0.4rem;">Ціна (грн)</label>
                    <input type="number" id="edit-price" required min="0" step="0.01" style="width:100%;padding:0.75rem;border:2px solid #E5E7EB;border-radius:8px;font-size:0.95rem;box-sizing:border-box;">
                </div>
                <div>
                    <label style="display:block;font-weight:600;margin-bottom:0.4rem;">Кількість</label>
                    <input type="number" id="edit-stock" required min="0" style="width:100%;padding:0.75rem;border:2px solid #E5E7EB;border-radius:8px;font-size:0.95rem;box-sizing:border-box;">
                </div>
            </div>
            <div style="margin-bottom:1rem;">
                <label style="display:block;font-weight:600;margin-bottom:0.4rem;">Бренд</label>
                <input type="text" id="edit-brand" style="width:100%;padding:0.75rem;border:2px solid #E5E7EB;border-radius:8px;font-size:0.95rem;box-sizing:border-box;">
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem;">
                <div>
                    <label style="display:block;font-weight:600;margin-bottom:0.4rem;">Стать</label>
                    <select id="edit-gender" style="width:100%;padding:0.75rem;border:2px solid #E5E7EB;border-radius:8px;font-size:0.95rem;box-sizing:border-box;">
                        <option value="унісекс">Унісекс</option>
                        <option value="чоловічий">Чоловічий</option>
                        <option value="жіночий">Жіночий</option>
                    </select>
                </div>
                <div>
                    <label style="display:block;font-weight:600;margin-bottom:0.4rem;">Тип</label>
                    <select id="edit-type" style="width:100%;padding:0.75rem;border:2px solid #E5E7EB;border-radius:8px;font-size:0.95rem;box-sizing:border-box;">
                        <option value="футболка">Футболка</option>
                        <option value="сорочка">Сорочка</option>
                        <option value="джинси">Джинси</option>
                        <option value="штани">Штани</option>
                        <option value="куртка">Куртка</option>
                        <option value="кросівки">Кросівки</option>
                        <option value="аксесуар">Аксесуар</option>
                        <option value="інше">Інше</option>
                    </select>
                </div>
            </div>
            <div style="margin-bottom:1.5rem;">
                <label style="display:block;font-weight:600;margin-bottom:0.4rem;">Розміри</label>
                <input type="text" id="edit-sizes" placeholder="XS:1,S:1,M:1,L:0" style="width:100%;padding:0.75rem;border:2px solid #E5E7EB;border-radius:8px;font-size:0.95rem;box-sizing:border-box;">
                <small style="color:#6B7280;font-size:0.8rem;">Формат: розмір:1 (є) або розмір:0 (немає)</small>
            </div>
            <div style="display:flex;gap:1rem;">
                <button type="button" onclick="closeEditModal()" style="flex:1;padding:0.875rem;border:2px solid #E5E7EB;border-radius:8px;background:white;font-size:0.95rem;cursor:pointer;font-weight:600;">Скасувати</button>
                <button type="submit" id="edit-submit-btn" style="flex:1;padding:0.875rem;border:none;border-radius:8px;background:#10B981;color:white;font-size:0.95rem;cursor:pointer;font-weight:600;">✓ Зберегти</button>
            </div>
        </form>
    </div>
</div>

<script>
function editProduct(id, name, price, stock, brand, sizes, gender, type) {
    document.getElementById('edit-id').value = id;
    document.getElementById('edit-name').value = name;
    document.getElementById('edit-price').value = price;
    document.getElementById('edit-stock').value = stock;
    document.getElementById('edit-brand').value = brand;
    document.getElementById('edit-sizes').value = sizes;
    document.getElementById('edit-gender').value = gender;
    document.getElementById('edit-type').value = type;
    document.getElementById('edit-modal').style.display = 'flex';
    var btn = document.getElementById('edit-submit-btn');
    btn.disabled = false;
    btn.textContent = '✓ Зберегти';
}
function closeEditModal() {
    document.getElementById('edit-modal').style.display = 'none';
}
function submitEditForm(e) {
    e.preventDefault();
    var id = document.getElementById('edit-id').value;
    var btn = document.getElementById('edit-submit-btn');
    btn.disabled = true;
    btn.textContent = '⏳ Збереження...';
    var data = {
        name: document.getElementById('edit-name').value,
        price: parseFloat(document.getElementById('edit-price').value),
        stock: parseInt(document.getElementById('edit-stock').value) || 0,
        brand: document.getElementById('edit-brand').value,
        sizes: document.getElementById('edit-sizes').value,
        gender: document.getElementById('edit-gender').value,
        type: document.getElementById('edit-type').value
    };
    fetch('/api/products/' + id, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(function(r) { return r.json(); })
    .then(function(d) {
        if (d.success) {
            closeEditModal();
            location.reload();
        } else if (d.error === 'Unauthorized') {
            alert('Сесія закінчилась. Увійдіть знову.');
            window.location.href = '/admin/login';
        } else {
            alert('Помилка: ' + (d.error || 'невідома'));
            btn.disabled = false;
            btn.textContent = '✓ Зберегти';
        }
    })
    .catch(function(err) {
        alert('Помилка: ' + err.message);
        btn.disabled = false;
        btn.textContent = '✓ Зберегти';
    });
}
document.getElementById('edit-modal').addEventListener('click', function(e) {
    if (e.target === this) closeEditModal();
});
</script>
'''

# Insert before </body>
last_body = content.rfind('</body>')
if last_body != -1:
    content = content[:last_body] + edit_modal + '\n</body>\n</html>'
else:
    content += edit_modal

open('templates/admin_dashboard.html', 'w', encoding='utf-8').write(content)

# Verify
c = open('templates/admin_dashboard.html', encoding='utf-8').read()
print('edit-modal count:', c.count('id="edit-modal"'))
print('submitEditForm count:', c.count('submitEditForm'))
print('editProduct count:', c.count('function editProduct'))
print('</html> count:', c.count('</html>'))
print('Total lines:', len(c.split('\n')))
