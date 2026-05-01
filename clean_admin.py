"""
Removes duplicate editProduct/submitEditForm/closeEditModal from the main script block,
keeping only the ones in the dedicated modal script at the end.
"""
import re

content = open('templates/admin_dashboard.html', encoding='utf-8').read()

# Step 1: Cut at first </html>
first_html = content.find('</html>')
if first_html != -1:
    content = content[:first_html + len('</html>')]

# Step 2: Remove the duplicate edit-modal div (keep only last one)
# Find all occurrences of edit-modal div
positions = []
pos = 0
while True:
    idx = content.find('<div id="edit-modal"', pos)
    if idx == -1:
        break
    positions.append(idx)
    pos = idx + 1

print(f'Found {len(positions)} edit-modal divs at positions: {positions}')

if len(positions) > 1:
    # Remove all but the last one
    for start_pos in reversed(positions[:-1]):
        # Find the closing </div> for this modal
        # Count nested divs
        depth = 0
        i = start_pos
        while i < len(content):
            if content[i:i+4] == '<div':
                depth += 1
                i += 4
            elif content[i:i+6] == '</div>':
                depth -= 1
                if depth == 0:
                    end_pos = i + 6
                    # Remove this modal div
                    content = content[:start_pos] + content[end_pos:]
                    print(f'Removed edit-modal at {start_pos}')
                    break
                i += 6
            else:
                i += 1

# Step 3: Remove duplicate script blocks with editProduct/submitEditForm
# Find all <script> blocks that contain editProduct
script_positions = []
pos = 0
while True:
    idx = content.find('<script>', pos)
    if idx == -1:
        idx = content.find('<script\n', pos)
        if idx == -1:
            break
    end_idx = content.find('</script>', idx)
    if end_idx == -1:
        break
    script_content = content[idx:end_idx+9]
    if 'editProduct' in script_content or 'submitEditForm' in script_content:
        script_positions.append((idx, end_idx + 9))
    pos = end_idx + 9

print(f'Found {len(script_positions)} script blocks with editProduct')

if len(script_positions) > 1:
    # Remove all but the last one
    for start, end in reversed(script_positions[:-1]):
        content = content[:start] + content[end:]
        print(f'Removed script block at {start}')

# Step 4: Ensure clean ending
last_body = content.rfind('</body>')
last_html = content.rfind('</html>')
if last_body != -1 and last_html != -1 and last_body < last_html:
    pass  # Good structure
elif last_body != -1:
    content = content[:last_body + 7] + '\n</html>'

open('templates/admin_dashboard.html', 'w', encoding='utf-8').write(content)

# Verify
c = open('templates/admin_dashboard.html', encoding='utf-8').read()
print('\n=== VERIFICATION ===')
print('edit-modal count:', c.count('id="edit-modal"'))
print('submitEditForm count:', c.count('submitEditForm'))
print('editProduct count:', c.count('function editProduct'))
print('</html> count:', c.count('</html>'))
print('</body> count:', c.count('</body>'))
print('Total lines:', len(c.split('\n')))
