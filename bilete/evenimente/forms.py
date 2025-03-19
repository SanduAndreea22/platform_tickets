from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

class RegisterForm(forms.Form):
    ROLE_CHOICES = [
        ('buyer', 'Cumpărător de bilete'),
        ('organizer', 'Organizator de evenimente')
    ]

    username = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nume'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Adresă de email'}))
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Parolă'}))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirmă Parola'}))
    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.RadioSelect(attrs={'class': 'form-check-input'}))

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")

        if password1 != password2:
            raise ValidationError("Parolele nu se potrivesc!")
        return password2

    def save(self):
        username = self.cleaned_data['username']
        email = self.cleaned_data['email']
        password1 = self.cleaned_data['password1']
        role = self.cleaned_data['role']

        # Crearea utilizatorului
        user = User.objects.create_user(username=username, email=email, password=password1)
        user.save()

        # Opțional: Poți salva rolul utilizatorului într-un model de tip UserProfile
        # Exemplu: UserProfile(user=user, role=role).save()

        return user

from django import forms
from django.contrib.auth.forms import AuthenticationForm

class LoginForm(AuthenticationForm):
    # Suprascrierea câmpului username pentru a folosi EmailField
    username = forms.EmailField(label='Adresă de email', max_length=255)
    password = forms.CharField(label='Parolă', widget=forms.PasswordInput)


# forms.py
from django import forms
from .models import Event

class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['name', 'description', 'date', 'location', 'category',
                  'tickets_available', 'image', 'theme', 'decorations', 'playlist']

from django import forms
from .models import Ticket

class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['ticket_type', 'quantity', 'discount', 'price']  # Adaugă 'price' aici
        widgets = {
            'discount': forms.NumberInput(attrs={'min': 0, 'max': 100, 'step': 1}),
            'price': forms.NumberInput(attrs={'min': 0, 'step': 0.01}),  # Poți adăuga și pentru 'price' un widget
        }

    # Dacă vrei să validezi că prețul este completat corect:
    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is None or price <= 0:
            raise forms.ValidationError("Prețul trebuie să fie mai mare decât 0.")
        return price


