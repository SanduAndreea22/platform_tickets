from django.contrib import admin

# Permite accesul tuturor utilizatorilor la Django Admin
admin.site.has_permission = lambda request: True

