import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from events.models import Event, Payment, Reservation, TicketType

DEMO_PARTICIPANTS = [
    {"username": "demo_ana", "email": "ana@demo.local", "first_name": "Ana", "last_name": "Popescu"},
    {"username": "demo_mihai", "email": "mihai@demo.local", "first_name": "Mihai", "last_name": "Ionescu"},
    {"username": "demo_elena", "email": "elena@demo.local", "first_name": "Elena", "last_name": "Dumitrescu"},
    {"username": "demo_radu", "email": "radu@demo.local", "first_name": "Radu", "last_name": "Georgescu"},
]

DEMO_ORGANIZERS = [
    {
        "username": "aurora_events",
        "email": "contact@auroraevents.demo",
        "first_name": "Aurora",
        "last_name": "Events",
    },
    {
        "username": "nexus_productions",
        "email": "hello@nexusproductions.demo",
        "first_name": "Nexus",
        "last_name": "Productions",
    },
]

DEMO_EVENTS = [
    {
        "organizer": "aurora_events",
        "title": "Summer Beats Festival",
        "description": (
            "A full day of live electronic and indie acts across two outdoor stages, "
            "with food trucks, chill-out zones, and a sunset headliner set."
        ),
        "location": "Herăstrău Park, București",
        "days_from_now": 21,
        "duration_hours": 10,
        "tickets": [
            ("Early Bird", "89.00", 60),
            ("General Admission", "129.00", 200),
            ("VIP Access", "299.00", 30),
        ],
    },
    {
        "organizer": "nexus_productions",
        "title": "Tech Forward Conference 2026",
        "description": (
            "A one-day conference on AI, cloud infrastructure, and product engineering, "
            "with talks from industry practitioners and hands-on afternoon workshops."
        ),
        "location": "Cluj Innovation Hub, Cluj-Napoca",
        "days_from_now": 35,
        "duration_hours": 8,
        "tickets": [
            ("Standard Pass", "249.00", 150),
            ("Student Pass", "99.00", 50),
            ("Workshop Add-on", "449.00", 40),
        ],
    },
    {
        "organizer": "aurora_events",
        "title": "Jazz Night at the Old Theatre",
        "description": (
            "An intimate evening of classic and contemporary jazz featuring a local quartet "
            "and a guest vocalist, in the historic Old Theatre concert hall."
        ),
        "location": "Old Theatre, Timișoara",
        "days_from_now": 14,
        "duration_hours": 3,
        "tickets": [
            ("General Seating", "69.00", 120),
            ("Front Row", "149.00", 25),
        ],
    },
    {
        "organizer": "nexus_productions",
        "title": "Stand-Up Comedy Live",
        "description": (
            "A night of stand-up comedy with three touring comedians, hosted in the city's "
            "favorite black-box theatre. Doors open 30 minutes before the show."
        ),
        "location": "Black Box Theatre, Iași",
        "days_from_now": 9,
        "duration_hours": 2,
        "tickets": [
            ("Standard Ticket", "59.00", 100),
        ],
    },
    {
        "organizer": "aurora_events",
        "title": "Mountain Trail Running Expo",
        "description": (
            "An expo and community meetup for trail runners, with gear demos, a short "
            "fun run through the foothills, and talks from ultra-marathon athletes."
        ),
        "location": "Poiana Brașov, Brașov",
        "days_from_now": 48,
        "duration_hours": 6,
        "tickets": [
            ("Expo Entry", "39.00", 300),
            ("Fun Run + Expo", "89.00", 150),
        ],
    },
    {
        "organizer": "nexus_productions",
        "title": "Contemporary Art Exhibition Opening",
        "description": (
            "Opening night for a new contemporary art exhibition featuring six emerging "
            "Romanian artists, with a guided walkthrough and a reception afterwards."
        ),
        "location": "MNAC, București",
        "days_from_now": 5,
        "duration_hours": 4,
        "tickets": [
            ("General Admission", "45.00", 180),
            ("Opening Night + Reception", "95.00", 60),
        ],
    },
]


class Command(BaseCommand):
    help = (
        "Seeds demo organizers, events, and ticket types so the site doesn't look "
        "empty. Idempotent: each event is looked up by title, so re-running this "
        "command never creates duplicates."
    )

    def handle(self, *args, **options):
        User = get_user_model()
        rng = random.Random(42)

        def get_or_create_user(data, is_organizer):
            user, created = User.objects.get_or_create(
                username=data["username"],
                defaults={
                    "email": data["email"],
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "is_organizer": is_organizer,
                    "is_participant": not is_organizer,
                },
            )
            if created:
                user.set_unusable_password()
                user.save()
                self.stdout.write(f"Created demo user '{user.username}'.")
            return user

        organizers = {
            data["username"]: get_or_create_user(data, is_organizer=True)
            for data in DEMO_ORGANIZERS
        }
        participants = [get_or_create_user(data, is_organizer=False) for data in DEMO_PARTICIPANTS]

        created_count = 0
        with transaction.atomic():
            for event_data in DEMO_EVENTS:
                if Event.objects.filter(title=event_data["title"]).exists():
                    continue

                start_date = timezone.now() + timedelta(days=event_data["days_from_now"])
                end_date = start_date + timedelta(hours=event_data["duration_hours"])

                event = Event.objects.create(
                    organizer=organizers[event_data["organizer"]],
                    title=event_data["title"],
                    description=event_data["description"],
                    location=event_data["location"],
                    start_date=start_date,
                    end_date=end_date,
                )

                for name, price, quantity in event_data["tickets"]:
                    ticket_type = TicketType.objects.create(
                        event=event,
                        name=name,
                        price=Decimal(price),
                        total_quantity=quantity,
                        available_quantity=quantity,
                    )

                    # Sell off a realistic chunk (30-60%) of this ticket type
                    # to real-looking confirmed reservations, so occupancy
                    # and revenue stats aren't all zero.
                    target_sold = int(quantity * rng.uniform(0.3, 0.6))
                    sold_so_far = 0
                    while sold_so_far < target_sold:
                        remaining = target_sold - sold_so_far
                        qty = min(remaining, rng.randint(1, 3))
                        buyer = rng.choice(participants)

                        reservation = Reservation.objects.create(
                            user=buyer,
                            ticket_type=ticket_type,
                            quantity=qty,
                            confirmed=True,
                        )
                        Payment.objects.create(
                            reservation=reservation,
                            amount=reservation.total_price,
                            status=Payment.STATUS_COMPLETED,
                            stripe_payment_intent=f"pi_demo_{reservation.ticket_code}",
                        )
                        ticket_type.available_quantity -= qty
                        sold_so_far += qty

                    ticket_type.save(update_fields=["available_quantity"])

                created_count += 1
                self.stdout.write(f"Created event '{event.title}'.")

        if created_count:
            self.stdout.write(self.style.SUCCESS(f"Seeded {created_count} new event(s)."))
        else:
            self.stdout.write("All demo events already exist, nothing to do.")
