import pathlib, re
base = pathlib.Path('c:/Users/ADMIN/Desktop/JOB TARGET SPACE')
ok = True

# 1. CSS brace balance
for name in ['css/style.css', 'css/pages.css']:
    t = (base / name).read_text(encoding='utf-8')
    bal = t.count('{') == t.count('}')
    ok = ok and bal
    print(f'{name}: braces {t.count("{")} / {t.count("}")} -> {"BALANCED" if bal else "UNBALANCED"}')

# 2. HTML tag balance + stylesheet order in <head>
for p in sorted(base.glob('*.html')):
    t = p.read_text(encoding='utf-8')
    tags = (t.count('<div') == t.count('</div>')
            and t.count('<section') == t.count('</section>')
            and t.count('<main') == t.count('</main>')
            and t.count('<footer') == t.count('</footer>')
            and t.count('<form') == t.count('</form>'))
    head = t.split('</head>')[0]
    links = re.findall(r'href="(css/[^"]+\.css)"', head)
    order_ok = bool(links) and links[0] == 'css/style.css'
    ok = ok and tags and order_ok
    print(f'{p.name}: tags {"OK" if tags else "BAD"} | head css {links} -> {"OK" if order_ok else "BAD"}')

# 3. FOUC: no JS css injection left
lj = (base / 'js/layout.js').read_text(encoding='utf-8')
no_inject = 'createElement' in lj
ok = ok and (not no_inject)
print('layout.js css-injection removed:', not no_inject)

print('RESULT:', 'ALL OK' if ok else 'ISSUES FOUND')
