from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .forms import LoginForm, RegisterForm, EventForm, TicketForm
from .models import Event, Ticket, Review
import stripe
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.contrib.auth.models import Group

# Configurare Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY



def home(request):
    # Nu mai preluăm evenimente din baza de date
    return render(request, 'home.html')

def about(request):
    return render(request, 'about.html')  # Vom crea un template numit about.html

def contact(request):
    return render(request, 'contact.html')

def terms(request):
    return render(request, 'term.html')

def privacy(request):
    return render(request, 'privacy.html')


def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()  # Crează utilizatorul
            role = form.cleaned_data['role']

            # Autentificare utilizator
            login(request, user)

            # Redirecționare în funcție de rol
            if role == 'organizer':
                return redirect('admin_dashboard')  # Redirecționare către dashboard-ul organizatorului
            else:
                return redirect('events_list')  # Redirecționare către pagina principală de evenimente

    else:
        form = RegisterForm()

    return render(request, 'register.html', {'form': form})



def user_login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            # Autentificare utilizator
            email = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                # Redirecționează utilizatorul în funcție de rol
                if user.is_organizer:
                    return redirect('admin_dashboard')  # Sau altă pagină a organizatorului
                else:
                    return redirect('events')  # Pagina pentru cumpărători de bilete
            else:
                messages.error(request, 'Email sau parolă incorectă!')
    else:
        form = LoginForm()

    return render(request, 'login.html', {'form': form})


def user_logout(request):
    logout(request)
    return redirect('login')  # Sau redirecționează unde dorești, de obicei la pagina de login


# Listă Evenimente pentru cumpărători
def events_list(request):
    # Preluăm evenimentele
    events = Event.objects.all()

    # Preluăm filtrele din GET
    category = request.GET.get('category', '')
    location = request.GET.get('location', '')
    date = request.GET.get('date', '')

    # Filtrăm evenimentele pe baza criteriilor
    if category:
        events = events.filter(category__icontains=category)
    if location:
        events = events.filter(location__icontains=location)
    if date:
        events = events.filter(date=date)

    # Returnăm template-ul și trimitem variabilele necesare
    return render(request, 'events_list.html', {
        'events': events,
        'category': category,  # Adăugăm category pentru preumplerea câmpului din formular
        'location': location,  # Adăugăm location pentru preumplerea câmpului din formular
        'date': date,          # Adăugăm date pentru preumplerea câmpului din formular
    })


# Detalii Eveniment pentru cumpărători
def event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    available_tickets = event.available_tickets()  # Verifică biletele disponibile pentru acest eveniment
    return render(request, 'event_detail.html', {
        'event': event,
        'available_tickets': available_tickets,
    })

def ticket_purchase(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    if request.method == "POST":
        ticket_type = request.POST['ticket_type']
        quantity = int(request.POST['quantity'])

        # Verificăm dacă există bilete de tipul selectat
        tickets = Ticket.objects.filter(event=event, ticket_type=ticket_type)

        if not tickets.exists():
            return render(request, 'ticket_purchase.html', {'event': event, 'error': 'Tipul de bilet nu există pentru acest eveniment.'})

        ticket = tickets.first()
        price = ticket.price * quantity

        # Crearea biletului pentru utilizator
        ticket_instance = Ticket.objects.create(
            user=request.user,
            event=event,
            ticket_type=ticket_type,
            quantity=quantity,
            price=price
        )

        # Crearea sesiunii Stripe pentru procesarea plății
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': f"{event.name} - {ticket_type}",
                        },
                        'unit_amount': int(price * 100),
                    },
                    'quantity': quantity,
                }],
                mode='payment',
                success_url=request.build_absolute_uri('/payment_success/'),
                cancel_url=request.build_absolute_uri('/payment_cancel/'),
            )
            return redirect(session.url, code=303)  # Redirect către Stripe pentru finalizarea plății
        except stripe.error.StripeError as e:
            messages.error(request, f"Eroare la procesarea plății: {str(e)}")
            return render(request, 'ticket_purchase.html', {'event': event, 'error': 'Eroare la procesarea plății. Te rugăm să încerci din nou.'})

    return render(request, 'ticket_purchase.html', {'event': event})

# Vizualizare bilete cumpărate de utilizator
def my_tickets(request):
    tickets = Ticket.objects.filter(user=request.user)
    return render(request, 'my_tickets.html', {'tickets': tickets})

# Căutare Evenimente
def search_results(request):
    query = request.GET.get('q', '')
    events = Event.objects.filter(name__icontains=query)
    return render(request, 'search_results.html', {'events': events})

# Adăugare recenzii pentru un eveniment
def reviews(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    reviews = Review.objects.filter(event=event)

    if request.method == "POST":
        rating = request.POST['rating']
        comment = request.POST['comment']
        Review.objects.create(user=request.user, event=event, rating=rating, comment=comment)

    return render(request, 'reviews.html', {'event': event, 'reviews': reviews})

# Funcție pentru gestionarea succesului plății
def payment_success(request):
    return render(request, 'payment_success.html')

# Funcție pentru gestionarea anulării plății
def payment_cancel(request):
    return render(request, 'payment_cancel.html')


# Dashboard Admin
def admin_dashboard(request):
    events = Event.objects.all()
    return render(request, 'admin_dashboard.html', {'events': events})

# Creare Eveniment
def create_event(request):
    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('admin_dashboard')
    else:
        form = EventForm()
    return render(request, 'create_event.html', {'form': form})

# Editare Eveniment
def edit_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            return redirect('admin_dashboard')
    else:
        form = EventForm(instance=event)
    return render(request, 'edit_event.html', {'form': form, 'event': event})

# Personalizare Eveniment
def customize_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if request.method == 'POST':
        event.theme = request.POST.get('theme')
        event.decorations = request.POST.get('decorations')
        event.playlist = request.POST.get('playlist')
        event.save()
        return redirect('admin_dashboard')
    return render(request, 'customize_event.html', {'event': event})

# Vânzare Bilete & Check-in
def ticket_management(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    tickets = event.tickets.all()  # Folosește 'tickets' în loc de 'ticket_set'
    if request.method == 'POST':
        form = TicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)  # Nu salvează încă în baza de date
            ticket.event = event  # Setează evenimentul corect
            ticket.user = request.user  # Asociază biletul cu utilizatorul curent
            ticket.save()  # Salvează obiectul Ticket
            return redirect('ticket_management', event_id=event.id)
    else:
        form = TicketForm()
    return render(request, 'ticket_management.html', {'event': event, 'tickets': tickets, 'form': form})

# Managementul Partenerilor
def partners(request):
    return render(request, 'partners.html')

# Statistici & Feedback
def event_statistics(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    return render(request, 'event_statistics.html', {'event': event})
