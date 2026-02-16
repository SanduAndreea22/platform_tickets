from django.test import TestCase
from django.urls import reverse
from .models import SupportMessage


class ContactPageTests(TestCase):
    def test_contact_get_returns_ok(self):
        response = self.client.get(reverse("pages:contact"))
        self.assertEqual(response.status_code, 200)

    def test_contact_post_valid_creates_message(self):
        response = self.client.post(
            reverse("pages:contact"),
            {
                "name": "Test User",
                "email": "user@example.com",
                "message": "Acesta este un mesaj valid.",
                "honeypot": "",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SupportMessage.objects.count(), 1)

    def test_contact_post_with_honeypot_is_rejected(self):
        response = self.client.post(
            reverse("pages:contact"),
            {
                "name": "Bot",
                "email": "bot@example.com",
                "message": "Mesaj aparent valid dar spam.",
                "honeypot": "spam",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SupportMessage.objects.count(), 0)
