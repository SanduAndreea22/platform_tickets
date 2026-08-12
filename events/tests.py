import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import stripe
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Event, Payment, Reservation, TicketType


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

        self.assertEqual(response.status_code, 200)
        reservation = Reservation.objects.get(user=self.participant, ticket_type=self.ticket)
        self.assertEqual(reservation.quantity, 1)


class PaymentFlowTestsBase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.organizer = User.objects.create_user(
            username="org_pay", password="pass", is_organizer=True
        )
        self.buyer = User.objects.create_user(
            username="buyer", password="pass", is_participant=True
        )
        self.event = Event.objects.create(
            organizer=self.organizer,
            title="Festival",
            description="Desc",
            location="Iasi",
            start_date=timezone.now() + timedelta(days=1),
            end_date=timezone.now() + timedelta(days=2),
        )
        self.ticket = TicketType.objects.create(
            event=self.event,
            name="GA",
            price=Decimal("20.00"),
            total_quantity=10,
            available_quantity=10,
        )
        self.reservation = Reservation.objects.create(
            user=self.buyer,
            ticket_type=self.ticket,
            quantity=2,
            confirmed=False,
        )


class CreatePaymentIntentTests(PaymentFlowTestsBase):
    @patch("events.views.stripe.PaymentIntent.create")
    def test_create_payment_intent_does_not_crash(self, mock_create):
        # Regression test: select_for_update() must run inside an atomic
        # block, otherwise this raises TransactionManagementError.
        mock_create.return_value = MagicMock(id="pi_123", client_secret="secret_123")
        self.client.login(username="buyer", password="pass")

        response = self.client.post(
            reverse("events:create_payment_intent", kwargs={"reservation_id": self.reservation.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["clientSecret"], "secret_123")

        payment = Payment.objects.get(reservation=self.reservation)
        self.assertEqual(payment.stripe_payment_intent, "pi_123")

    @patch("events.views.stripe.PaymentIntent.create")
    def test_create_payment_intent_rejects_already_paid(self, mock_create):
        self.reservation.confirmed = True
        self.reservation.save()
        self.client.login(username="buyer", password="pass")

        response = self.client.post(
            reverse("events:create_payment_intent", kwargs={"reservation_id": self.reservation.id})
        )

        self.assertEqual(response.status_code, 400)
        mock_create.assert_not_called()


class PaymentSuccessTests(PaymentFlowTestsBase):
    def setUp(self):
        super().setUp()
        self.payment = Payment.objects.create(
            reservation=self.reservation,
            amount=self.reservation.total_price,
            stripe_payment_intent="pi_456",
        )

    @patch("events.views.stripe.PaymentIntent.retrieve")
    def test_payment_success_confirms_when_stripe_says_succeeded(self, mock_retrieve):
        mock_retrieve.return_value = MagicMock(status="succeeded")
        self.client.login(username="buyer", password="pass")

        self.client.get(reverse("events:payment_success"), {"payment_intent": "pi_456"})

        self.reservation.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertTrue(self.reservation.confirmed)
        self.assertEqual(self.payment.status, Payment.STATUS_COMPLETED)

    @patch("events.views.stripe.PaymentIntent.retrieve")
    def test_payment_success_does_not_bypass_unpaid_intent(self, mock_retrieve):
        # Regression test for the payment-bypass bug: navigating to this URL
        # with a real but unpaid PaymentIntent must NOT confirm the reservation.
        mock_retrieve.return_value = MagicMock(status="requires_payment_method")
        self.client.login(username="buyer", password="pass")

        self.client.get(reverse("events:payment_success"), {"payment_intent": "pi_456"})

        self.reservation.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertFalse(self.reservation.confirmed)
        self.assertNotEqual(self.payment.status, Payment.STATUS_COMPLETED)

    @patch("events.views.stripe.PaymentIntent.retrieve")
    def test_payment_success_ignores_other_users_payment(self, mock_retrieve):
        mock_retrieve.return_value = MagicMock(status="succeeded")
        other_user = get_user_model().objects.create_user(
            username="other", password="pass", is_participant=True
        )
        self.client.login(username="other", password="pass")

        self.client.get(reverse("events:payment_success"), {"payment_intent": "pi_456"})

        self.reservation.refresh_from_db()
        self.assertFalse(self.reservation.confirmed)


class StripeWebhookTests(PaymentFlowTestsBase):
    def setUp(self):
        super().setUp()
        self.payment = Payment.objects.create(
            reservation=self.reservation,
            amount=self.reservation.total_price,
            stripe_payment_intent="pi_789",
        )

    def test_webhook_rejects_invalid_signature(self):
        with patch(
            "events.views.stripe.Webhook.construct_event",
            side_effect=stripe.error.SignatureVerificationError("bad signature", "sig"),
        ):
            response = self.client.post(
                reverse("events:stripe_webhook"),
                data=json.dumps({}),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="bad",
            )

        self.assertEqual(response.status_code, 400)

    def test_webhook_confirms_reservation_on_succeeded_event(self):
        fake_event = {
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_789"}},
        }
        with patch("events.views.stripe.Webhook.construct_event", return_value=fake_event):
            response = self.client.post(
                reverse("events:stripe_webhook"),
                data=json.dumps({}),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="sig",
            )

        self.assertEqual(response.status_code, 200)
        self.reservation.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertTrue(self.reservation.confirmed)
        self.assertEqual(self.payment.status, Payment.STATUS_COMPLETED)


class ExpireReservationsCommandTests(PaymentFlowTestsBase):
    def test_expired_unconfirmed_reservation_releases_stock(self):
        self.ticket.reserve(self.reservation.quantity)
        self.reservation.expires_at = timezone.now() - timedelta(minutes=1)
        self.reservation.save()

        call_command("expire_reservations")

        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.available_quantity, self.ticket.total_quantity)
        self.assertFalse(Reservation.objects.filter(id=self.reservation.id).exists())

    def test_confirmed_reservation_is_not_expired(self):
        self.reservation.confirmed = True
        self.reservation.expires_at = timezone.now() - timedelta(minutes=1)
        self.reservation.save()

        call_command("expire_reservations")

        self.assertTrue(Reservation.objects.filter(id=self.reservation.id).exists())
