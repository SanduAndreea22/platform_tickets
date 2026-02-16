from django.urls import path
from . import views
app_name = "pages"

urlpatterns = [
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('terms/', views.terms, name='terms'),
    path('privacy/', views.privacy, name='privacy'),
    path('partners/', views.partners, name='partners'),
    path('', views.home, name='home'),
]

