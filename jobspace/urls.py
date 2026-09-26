from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("website.urls")),
]

# User-uploaded files (CVs) must stay reachable in production. The
# debug-only static() helper below is not available when DEBUG is False,
# which is what Render runs, so media is served explicitly here.
urlpatterns += [
    re_path(
        r"^media/(?P<path>.*)$",
        serve,
        {"document_root": str(settings.MEDIA_ROOT)},
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")
