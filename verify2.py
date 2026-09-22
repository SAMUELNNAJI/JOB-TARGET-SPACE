import pathlib
base = pathlib.Path('c:/Users/ADMIN/Desktop/JOB TARGET SPACE')

# 1. Home removed from every page
home = [p.name for p in base.glob('*.html') if '>Home<' in p.read_text(encoding='utf-8')]
print('pages still having Home link:', home if home else 'NONE (all 8 cleared)')

# 2. index hero checks
t = (base / 'index.html').read_text(encoding='utf-8')
print('pexels left:', 'pexels' in t)
for i in (1, 2, 3):
    print(f'hero{i}.jpg refs:', t.count(f'hero{i}.jpg'))
print('hero slides:', t.count('class="hero-slide'))
print('counter / 03:', '/ 03' in t)
divs = (t.count('<div'), t.count('</div>'))
print('div balance:', divs, 'OK' if divs[0] == divs[1] else 'BROKEN')
secs = (t.count('<section'), t.count('</section>'))
print('section balance:', secs, 'OK' if secs[0] == secs[1] else 'BROKEN')

# 3. image files exist
for i in (1, 2, 3):
    print(f'hero{i}.jpg exists:', (base / f'hero{i}.jpg').is_file())

# 4. progress math in main.js
js = (base / 'js/main.js').read_text(encoding='utf-8')
print('progress uses slides.length:', 'slides.length' in js, '| old 33.33 hardcoded:', '33.33' in js)

# 5. css progress initial width + brace balance
css = (base / 'css/style.css').read_text(encoding='utf-8')
print('progress initial 33.34%:', 'width:33.34%' in css)
print('css braces:', css.count('{'), css.count('}'),
      'BALANCED' if css.count('{') == css.count('}') else 'UNBALANCED')
print('DONE')
