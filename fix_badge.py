content = open('templates/index.html', encoding='utf-8').read()
old = '{% if product.stock > 0 and product.stock <= 5 %}'
new = '{% if product.stock == 1 %}'
old2 = '<div class="stock-badge">⚠️ Залишилось {{ product.stock }} шт</div>'
new2 = '<div class="stock-badge">⚠️ Залишилась 1 шт</div>'
content = content.replace(old, new).replace(old2, new2)
open('templates/index.html', 'w', encoding='utf-8').write(content)
print('Done')
