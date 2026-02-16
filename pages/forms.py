from django import forms
from .models import SupportMessage


class ContactForm(forms.ModelForm):
    honeypot = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = SupportMessage
        fields = ["name", "email", "message"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "input",
                "placeholder": "Full name"
            }),
            "email": forms.EmailInput(attrs={
                "class": "input",
                "placeholder": "Email address"
            }),
            "message": forms.Textarea(attrs={
                "class": "textarea",
                "placeholder": "Write your message...",
                "rows": 4
            }),
        }

    def clean_honeypot(self):
        data = self.cleaned_data.get("honeypot")
        if data:
            raise forms.ValidationError("Spam detected.")
        return data

    def clean_message(self):
        message = self.cleaned_data.get("message", "")
        if len(message) < 10:
            raise forms.ValidationError("Message is too short.")
        return message

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if not forms.EmailField().clean(email):
            raise forms.ValidationError("Invalid email address.")
        return email


