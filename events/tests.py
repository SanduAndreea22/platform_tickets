from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Event, Reservation, TicketType


class TicketTypeModelTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="org", password="pass", is_organizer=True
        )
        self.event = Event.objects.create(
            organizer=user,
            title="Concert",
            description="Desc",
            location="Cluj",
            start_date=timezone.now() + timedelta(days=1),
            end_date=timezone.now() + timedelta(days=2),
        )
        self.ticket = TicketType.objects.create(
            event=self.event,
            name="Standard",
            price="100.00",
            total_quantity=10,
            available_quantity=10,
        )

    def test_reserve_raises_when_not_enough_stock(self):
        with self.assertRaises(ValidationError):
            self.ticket.reserve(11)

    def test_release_never_exceeds_total_quantity(self):
        self.ticket.reserve(3)
        self.ticket.release(10)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.available_quantity, self.ticket.total_quantity)


class EventDetailReservationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.organizer = User.objects.create_user(
            username="org", password="pass", is_organizer=True
        )
        self.participant = User.objects.create_user(
            username="part", password="pass", is_participant=True
        )
        self.event = Event.objects.create(
            organizer=self.organizer,
            title="Tech Meetup",
            description="Desc",
            location="Bucuresti",
            start_date=timezone.now() + timedelta(days=1),
            end_date=timezone.now() + timedelta(days=2),
        )
        self.ticket = TicketType.objects.create(
            event=self.event,
            name="Early Bird",
            price="50.00",
            total_quantity=5,
            available_quantity=5,
        )

    def test_invalid_quantity_defaults_to_one(self):
        self.client.login(username="part", password="pass")

        response = self.client.post(
            reverse("events:event_detail", kwargs={"pk": self.event.id}),
            {"ticket_id": self.ticket.id, "quantity": "abc"},
            follow=True,
        )

# Create your tests here.
        self.assertEqual(response.status_code, 200)
        reservation = Reservation.objects.get(user=self.participant, ticket_type=self.ticket)
        self.assertEqual(reservation.quantity, 1)
