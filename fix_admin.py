content = open('templates/admin_dashboard.html', encoding='utf-8').read()

# Знаходимо перший </html> і обрізаємо все після нього
first_html_close = content.find('</html>')
if first_html_close != -1:
    content = content[:first_html_close + len('</html>')]
    open('templates/admin_dashboard.html', 'w', encoding='utf-8').write(content)
    print('Done. File length:', len(content))
else:
    print('</html> not found')
