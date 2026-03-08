from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls), # Nu uita de admin, e util pentru management!
    path("", include(("pages.urls", "pages"), namespace="pages")),
    path("users/", include(("users.urls", "users"), namespace="users")),
    path("events/", include(("events.urls", "events"), namespace="events")),
]

# Această linie "leagă" folderul media de serverul tău de dezvoltare
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

