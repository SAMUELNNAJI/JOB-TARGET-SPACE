import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'jobspace.settings'
django.setup()
from django.template.loader import get_template
for t in ['auth/signin.html','auth/signup.html','base.html','terms.html','privacy.html']:
    try:
        get_template(t)
        print('OK  ', t)
    except Exception as e:
        print('ERR ', t, e)
