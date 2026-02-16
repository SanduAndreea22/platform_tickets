from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

# Create your tests here.

class UserFlowTests(TestCase):
    def test_register_participant(self):
        response = self.client.post(
            reverse("users:register"),
            {
                "username": "participant1",
                "email": "participant1@example.com",
                "password": "secret123",
                "role": "participant",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        user = get_user_model().objects.get(username="participant1")
        self.assertTrue(user.is_participant)
        self.assertFalse(user.is_organizer)

    def test_register_organizer(self):
        response = self.client.post(
            reverse("users:register"),
            {
                "username": "organizer1",
                "email": "organizer1@example.com",
                "password": "secret123",
                "role": "organizer",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        user = get_user_model().objects.get(username="organizer1")
        self.assertTrue(user.is_organizer)
        self.assertFalse(user.is_participant)

    def test_login_success(self):
        get_user_model().objects.create_user(
            username="loginuser",
            email="login@example.com",
            password="secret123",
            is_participant=True,
        )

        response = self.client.post(
            reverse("users:login"),
            {"username": "loginuser", "password": "secret123"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_logout_redirects_to_login(self):
        get_user_model().objects.create_user(
            username="logoutuser",
            email="logout@example.com",
            password="secret123",
        )
        self.client.login(username="logoutuser", password="secret123")

        response = self.client.get(reverse("users:logout"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

