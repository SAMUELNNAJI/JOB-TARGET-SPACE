from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from website import seo_views

# Custom error pages. These MUST be the last entries in the root urlconf —
# handler404 in particular is a catch-all, so anything added after it becomes
# unreachable.
#
#   404 → templates/404.html  the searching magnifier
#   403 → templates/403.html  the padlock (raised by the protected downloads)
#   500 → templates/500.html  the jammed gear (self-contained by necessity)
#
# Each is a standalone page with inline CSS and no {% extends %}. For 500 that
# is mandatory, not a preference: see the comment at the top of that template.
urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("website.urls")),
    # SEO endpoints. Kept in the root urlconf because search engines look for
    # them at the site root, not under the app prefix.
    path("sitemap.xml", seo_views.sitemap, name="sitemap"),
    path("robots.txt", seo_views.robots_txt, name="robots_txt"),
]

handler403 = "jobspace.error_views.permission_denied"
handler404 = "jobspace.error_views.page_not_found"
handler500 = "jobspace.error_views.server_error"

# NOTE: there is deliberately NO /media/ route here.
#
# It used to serve every uploaded file to anyone who knew the URL, which
# exposed candidate CVs, employer payment proofs and chat voice notes without
# authentication. Uploads are now served exclusively by the permission-checked
# views in website/views.py:
#
#   /documents/<id>/download/     a CV          — its owner, or staff
#   /payments/<id>/proof/         a receipt     — the paying employer, or staff
#   /support/messages/<id>/audio/ a voice note  — the participants, or staff
#
# Do not add a catch-all media route back. It would silently undo that.
# Static assets come from WhiteNoise; the optional nginx block in
# deploy/nginx/jobspace.conf serves /static/ only.

if settings.DEBUG:
    # In development Django serves media from the URL recorded in the database.
    # That is acceptable on a laptop and must never reach production, which is
    # why the guard above has no DEBUG-independent branch.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
