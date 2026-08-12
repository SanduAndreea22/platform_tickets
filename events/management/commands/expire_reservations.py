import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from events.models import Reservation

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Releases stock held by unconfirmed reservations whose hold "
        "window has expired, then deletes them. Intended to run "
        "periodically (cron / Windows Task Scheduler / Celery beat)."
    )

    def handle(self, *args, **options):
        expired = Reservation.objects.filter(
            confirmed=False,
            expires_at__lt=timezone.now(),
        ).select_related("ticket_type")

        released = 0
        for reservation in expired:
            with transaction.atomic():
                ticket_type = type(reservation.ticket_type).objects.select_for_update().get(
                    pk=reservation.ticket_type_id
                )
                ticket_type.release(reservation.quantity)
                reservation.delete()
            released += 1

        if released:
            logger.info("Released %d expired reservation(s).", released)
        self.stdout.write(self.style.SUCCESS(f"Released {released} expired reservation(s)."))
