from django.conf import settings


def currency(request):
    return {"CURRENCY": settings.STRIPE_CURRENCY.upper()}
