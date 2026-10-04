import os, sys, django, urllib.request, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")
django.setup()

from django.core.files import File
from website.models import BlogPost

# One remaining image — graduates post
slug = "why-nigerian-graduates-getting-rejected"
url  = "https://images.unsplash.com/photo-1523240795612-9a054b0db644?w=800&q=80"
fname = "graduates.jpg"

try:
    post = BlogPost.objects.get(slug=slug)
    if post.cover_image:
        print(f"Already has image: {post.cover_image.name}")
    else:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            urllib.request.urlretrieve(url, tmp.name)
            with open(tmp.name, "rb") as f:
                post.cover_image.save(fname, File(f), save=True)
        print(f"OK: saved image for {slug}")
except Exception as e:
    print(f"ERROR: {e}")

print("\nAll posts:")
for p in BlogPost.objects.all():
    status = p.cover_image.name if p.cover_image else "NO IMAGE"
    print(f"  {p.slug[:50]:<50}  {status}")
