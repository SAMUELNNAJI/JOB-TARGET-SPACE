import re, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jobspace.settings')
import django; django.setup()

results = []

# 1. Template parse check
from django.template.loader import get_template
for t in [
    'dashboard/employer/index.html',
    'dashboard/employer/profile.html',
    'dashboard/employer/shortlist.html',
    'dashboard/employer/subscription.html',
    'dashboard/employer/section.html',
    'dashboard/base.html',
]:
    try:
        get_template(t)
        results.append(f'TEMPLATE OK  : {t}')
    except Exception as e:
        results.append(f'TEMPLATE ERR : {t} — {e}')

css = open('static/css/dashboard.css', encoding='utf-8').read()

# 2. emp-* CSS coverage across all employer templates
all_emp_classes = set()
for fname in [
    'templates/dashboard/employer/index.html',
    'templates/dashboard/employer/profile.html',
    'templates/dashboard/employer/shortlist.html',
    'templates/dashboard/employer/subscription.html',
    'templates/dashboard/employer/section.html',
]:
    html = open(fname, encoding='utf-8').read()
    for m in re.findall(r'class="([^"]*)"', html):
        for c in m.split():
            if c.startswith('emp-'):
                all_emp_classes.add(c)

css_emp = set(re.findall(r'\.(emp-[\w-]+)', css))
# Filter out false positives (Django template expressions)
real_missing = sorted(c for c in all_emp_classes - css_emp if '{{' not in c and '{%' not in c)

results.append(f'emp-* HTML classes : {len(all_emp_classes)}')
results.append(f'emp-* CSS selectors: {len(css_emp)}')
results.append('emp-* CSS coverage : ' + ('PASS' if not real_missing else 'MISSING: ' + ', '.join(real_missing)))

# 3. Django system check
import subprocess
r = subprocess.run([sys.executable, 'manage.py', 'check'], capture_output=True, text=True)
results.append('manage.py check   : ' + (r.stdout.strip() or r.stderr.strip()))

with open('verify_emp_result.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(results) + '\n')
print('done')
