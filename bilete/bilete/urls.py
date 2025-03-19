from django.contrib import admin
from django.urls import path, include  # include este necesar pentru a include rutele aplicației

urlpatterns = [
    path('admin/', admin.site.urls),  # Ruta pentru panoul de administrare
    path('', include('evenimente.urls')),  # Include rutele aplicației 'evenimente' (pentru pagina home și altele)
]
