from django.contrib import admin
from .models import Event, TicketType, Reservation, Payment

admin.site.register(Event)
admin.site.register(TicketType)
admin.site.register(Reservation)
admin.site.register(Payment)
