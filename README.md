# JobSpace Django site

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000/.

The existing design is rendered through the `website` app. Clean Django routes are available for each page, and the original `.html` URLs remain supported while links are migrated.
