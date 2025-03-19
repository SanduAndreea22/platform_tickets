from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('terms/', views.terms, name='terms'),
    path('privacy/', views.privacy, name='privacy'),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('payment_success/', views.payment_success, name='payment_success'),
    path('payment_cancel/', views.payment_cancel, name='payment_cancel'),
    path('events/', views.events_list, name='events_list'),
    path('event/<int:event_id>/', views.event_detail, name='event_detail'),
    path('event/<int:event_id>/purchase/', views.ticket_purchase, name='ticket_purchase'),
    path('my_tickets/', views.my_tickets, name='my_tickets'),
    path('search/', views.search_results, name='search_results'),
    path('event/<int:event_id>/reviews/', views.reviews, name='reviews'),
    path('organizer/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('event/create/', views.create_event, name='create_event'),
    path('event/<int:event_id>/edit/', views.edit_event, name='edit_event'),
    path('event/<int:event_id>/customize/', views.customize_event, name='customize_event'),
    path('event/<int:event_id>/tickets/', views.ticket_management, name='ticket_management'),
    path('partners/', views.partners, name='partners'),
    path('event/<int:event_id>/statistics/', views.event_statistics, name='event_statistics'),

]
