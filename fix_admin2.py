content = open('templates/admin_dashboard.html', encoding='utf-8').read()

# Видаляємо залишки старого коду між двома product-form listeners
bad1 = """        document.getElementById('product-form').addEventListener('submit', function(e) {
            .catch(err => alert('Помилка: ' + err.message));
        });
        
        document.getElementById('product-form').addEventListener('submit', function(e) {"""

good1 = """        document.getElementById('product-form').addEventListener('submit', function(e) {"""

if bad1 in content:
    content = content.replace(bad1, good1)
    print('Fixed duplicate product-form listener')
else:
    print('Pattern not found, trying alternative...')
    # Знаходимо перший product-form listener з .catch залишком
    import re
    # Видаляємо перший неповний listener
    pattern = r"document\.getElementById\('product-form'\)\.addEventListener\('submit', function\(e\) \{\s*\.catch\(err => alert\('Помилка: ' \+ err\.message\)\);\s*\}\);\s*"
    content = re.sub(pattern, '', content)
    print('Removed incomplete listener')

open('templates/admin_dashboard.html', 'w', encoding='utf-8').write(content)
print('Done')
