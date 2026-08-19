from django.contrib import admin
from .models import Event, TicketType, Reservation, Payment


class TicketTypeInline(admin.TabularInline):
    model = TicketType
    extra = 0


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "organizer", "start_date", "end_date")
    list_filter = ("start_date",)
    search_fields = ("title", "location", "organizer__username")
    inlines = [TicketTypeInline]


@admin.register(TicketType)
class TicketTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "event", "price", "available_quantity", "total_quantity")
    list_filter = ("event",)
    search_fields = ("name", "event__title")


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("user", "ticket_type", "quantity", "confirmed", "created_at")
    list_filter = ("confirmed", "created_at")
    search_fields = ("user__username", "ticket_code")
    readonly_fields = ("ticket_code", "created_at")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reservation", "amount", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("reservation__user__username", "stripe_payment_intent")

    # Stripe identifiers stay visible for support/debugging, but locked to
    # read-only so staff can't hand-edit a payment's recorded state, and
    # payments can't be created/deleted from the admin (they're a byproduct
    # of the checkout flow, not a standalone record staff should manage).
    readonly_fields = (
        "reservation",
        "amount",
        "status",
        "stripe_payment_intent",
        "stripe_client_secret",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
