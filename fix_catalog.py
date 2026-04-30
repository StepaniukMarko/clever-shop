content = open('templates/index.html', encoding='utf-8').read()

# Знаходимо другий каталог - від другого "product-grid" до "BRANDS SECTION"
import re

# Знаходимо позицію другого входження product-grid
first = content.find('id="products-container"')
second = content.find('id="products-container"', first + 1)

if second == -1:
    print('Дублікат не знайдений')
else:
    # Знаходимо початок другого aside (filters) перед другим products-container
    # Шукаємо "BRANDS SECTION" після другого каталогу
    brands_pos = content.find('<!-- BRANDS SECTION -->', second)
    
    # Знаходимо початок другого aside - шукаємо назад від second
    # Шукаємо другий <aside class="filters"
    aside_positions = [m.start() for m in re.finditer(r'<aside class="filters"', content)]
    
    if len(aside_positions) >= 2:
        second_aside = aside_positions[1]
        # Знаходимо </section> перед brands
        section_end = content.rfind('</section>', second, brands_pos)
        
        # Видаляємо від другого aside до кінця другого </section>
        to_remove = content[second_aside:section_end + len('</section>')]
        content = content.replace(to_remove, '', 1)
        open('templates/index.html', 'w', encoding='utf-8').write(content)
        print(f'Видалено {len(to_remove)} символів дублікату')
    else:
        print('Другий aside не знайдений')
