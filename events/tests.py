import json
import threading
from datetime import timedelta
from decimal import Decimal
from unittest import skipUnless
from unittest.mock import MagicMock, patch

import stripe
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, TransactionTestCase
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


@skipUnless(
    connection.vendor == "postgresql",
    "select_for_update() row locking is only meaningfully enforced on "
    "PostgreSQL (production/Neon here) — SQLite's has_select_for_update "
    "is False, so Django silently skips the FOR UPDATE clause and this "
    "test would be flaky for reasons unrelated to the fix being tested.",
)
class ConcurrentReservationTests(TransactionTestCase):
    """
    Regression test for the race condition fixed in event_detail: two
    simultaneous requests for the same last ticket must not both succeed.
    Uses TransactionTestCase (real, separate DB connections per thread)
    instead of TestCase, since TestCase wraps everything in one shared
    transaction and would hide any real locking behavior.
    """

    def setUp(self):
        User = get_user_model()
        self.organizer = User.objects.create_user(
            username="org_race", password="pass", is_organizer=True
        )
        self.buyer_a = User.objects.create_user(
            username="buyer_a", password="pass", is_participant=True
        )
        self.buyer_b = User.objects.create_user(
            username="buyer_b", password="pass", is_participant=True
        )
        self.event = Event.objects.create(
            organizer=self.organizer,
            title="Sold Out Soon",
            description="Desc",
            location="Loc",
            start_date=timezone.now() + timedelta(days=1),
            end_date=timezone.now() + timedelta(days=2),
        )
        self.ticket = TicketType.objects.create(
            event=self.event,
            name="Last Ticket",
            price=Decimal("50.00"),
            total_quantity=1,
            available_quantity=1,
        )

    def test_two_simultaneous_buyers_cannot_both_get_the_last_ticket(self):
        barrier = threading.Barrier(2)
        results = {}

        def attempt(username, key):
            from django.test import Client

            client = Client(SERVER_NAME="127.0.0.1")
            client.login(username=username, password="pass")
            barrier.wait()  # line both requests up to hit the view at the same time
            try:
                response = client.post(
                    reverse("events:event_detail", kwargs={"pk": self.event.id}),
                    {"ticket_id": self.ticket.id, "quantity": 1},
                )
                results[key] = response
            except Exception as exc:
                results[key] = exc

        t1 = threading.Thread(target=attempt, args=("buyer_a", "a"))
        t2 = threading.Thread(target=attempt, args=("buyer_b", "b"))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        for key, result in results.items():
            if isinstance(result, Exception):
                self.fail(f"Request '{key}' raised an unexpected exception: {result!r}")

        confirmed_reservations = Reservation.objects.filter(ticket_type=self.ticket)
        self.assertEqual(
            confirmed_reservations.count(), 1,
            "Both concurrent requests created a reservation for the single remaining ticket.",
        )

        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.available_quantity, 0)
        self.assertGreaterEqual(self.ticket.available_quantity, 0)


class OrganizerDashboardTests(TestCase):
    """Covers the redesigned organizer dashboard and that every redesigned
    page still renders for the right role."""

    def setUp(self):
        User = get_user_model()
        self.org = User.objects.create_user("org1", password="pw", is_organizer=True, is_participant=False)
        self.other_org = User.objects.create_user("org2", password="pw", is_organizer=True, is_participant=False)
        self.part = User.objects.create_user("part1", password="pw")
        self.event = Event.objects.create(
            organizer=self.org, title="Show", description="d", location="Cluj",
            start_date=timezone.now() + timedelta(days=3), end_date=timezone.now() + timedelta(days=4),
        )
        self.ticket = TicketType.objects.create(
            event=self.event, name="GA", price="50.00", total_quantity=10, available_quantity=7,
        )
        self.paid = Reservation.objects.create(user=self.part, ticket_type=self.ticket, quantity=2, confirmed=True)
        Reservation.objects.create(user=self.part, ticket_type=self.ticket, quantity=1, confirmed=False)

    def test_dashboard_requires_login(self):
        resp = self.client.get(reverse("events:organizer_dashboard"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/users/login/", resp.url)

    def test_participant_cannot_open_dashboard(self):
        self.client.force_login(self.part)
        resp = self.client.get(reverse("events:organizer_dashboard"))
        self.assertRedirects(resp, reverse("pages:home"), fetch_redirect_response=False)

    def test_dashboard_kpis(self):
        self.client.force_login(self.org)
        resp = self.client.get(reverse("events:organizer_dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["revenue"], Decimal("100.00"))
        self.assertEqual(resp.context["tickets_sold"], 2)
        self.assertEqual(resp.context["pending_count"], 1)
        self.assertEqual(len(resp.context["series"]), 30)
        self.assertEqual(sum(d["tickets"] for d in resp.context["series"]), 2)

    def test_dashboard_only_counts_own_events(self):
        self.client.force_login(self.other_org)
        resp = self.client.get(reverse("events:organizer_dashboard"))
        self.assertEqual(resp.context["revenue"], Decimal("0"))
        self.assertEqual(resp.context["event_count"], 0)

    def test_organizer_pages_render(self):
        self.client.force_login(self.org)
        e = self.event.id
        for name, args in [
            ("events:my_events", []), ("events:create_event", []), ("events:edit_event", [e]),
            ("events:customize_event", [e]), ("events:ticket_management", [e]),
            ("events:ticket_checkin", [self.paid.ticket_code]),
        ]:
            with self.subTest(name):
                self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200)

    def test_participant_pages_render(self):
        self.client.force_login(self.part)
        for name, args in [
            ("events:my_tickets", []), ("events:my_reservations", []),
            ("events:payment_page", [self.paid.id]), ("events:payment_cancel", []),
            ("events:event_detail", [self.event.id]), ("events:events_list", []),
            ("users:profile", []), ("pages:home", []),
        ]:
            with self.subTest(name):
                self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200)

    def test_public_pages_render_anonymously(self):
        for name in ["pages:home", "pages:about", "pages:terms", "pages:privacy", "pages:partners",
                     "pages:how_it_works", "pages:contact", "users:login", "users:register",
                     "users:password_reset", "events:events_list"]:
            with self.subTest(name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_login_form_does_not_post_literal_none_as_next(self):
        resp = self.client.get(reverse("users:login"))
        self.assertNotContains(resp, 'value="None"')
        resp = self.client.post(reverse("users:login"), {"username": "part1", "password": "pw", "next": ""})
        self.assertRedirects(resp, reverse("users:profile"), fetch_redirect_response=False)


class PaginationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        org = User.objects.create_user("porg", password="pw", is_organizer=True, is_participant=False)
        self.part = User.objects.create_user("ppart", password="pw")
        now = timezone.now()
        for i in range(14):
            ev = Event.objects.create(organizer=org, title=f"Ev {i}", description="d", location="X",
                                      start_date=now + timedelta(days=i + 1), end_date=now + timedelta(days=i + 2))
            tt = TicketType.objects.create(event=ev, name="GA", price="10", total_quantity=5, available_quantity=4)
            Reservation.objects.create(user=self.part, ticket_type=tt, quantity=1, confirmed=True)

    def test_events_list_is_paginated_and_keeps_filters(self):
        r = self.client.get(reverse("events:events_list"), {"q": "Ev"})
        self.assertEqual(len(r.context["events"]), 12)
        self.assertContains(r, "page=2&amp;q=Ev")
        r2 = self.client.get(reverse("events:events_list"), {"q": "Ev", "page": 2})
        self.assertEqual(len(r2.context["events"]), 2)

    def test_my_tickets_is_paginated(self):
        self.client.force_login(self.part)
        r = self.client.get(reverse("events:my_tickets"))
        self.assertEqual(len(r.context["tickets"]), 6)
        self.assertEqual(r.context["page_obj"].paginator.count, 14)
        self.assertEqual(self.client.get(reverse("events:my_tickets"), {"page": 99}).status_code, 200)
