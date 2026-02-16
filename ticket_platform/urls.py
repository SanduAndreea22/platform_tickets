from django.urls import include, path

urlpatterns = [
    path("", include(("pages.urls", "pages"), namespace="pages")),
    path("users/", include(("users.urls", "users"), namespace="users")),
    path("events/", include(("events.urls", "events"), namespace="events")),
    # rutele aplicației tale
]

