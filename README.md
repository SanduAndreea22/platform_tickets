
# 🎟️ Event Ticketing Platform

Platformă web pentru **gestionarea evenimentelor și vânzarea de bilete online**, dezvoltată cu **Django** și integrată cu **Stripe** pentru plăți securizate.

Acest proiect permite organizatorilor să creeze și să administreze evenimente, iar participanților să rezerve și să plătească bilete online.

---

## 🚀 Funcționalități

### 👤 Utilizatori
- Înregistrare și autentificare
- Roluri:
  - **Participant** – rezervare și plată bilete
  - **Organizer** – creare și administrare evenimente
- Profil utilizator

### 📅 Evenimente
- Listare evenimente
- Căutare după titlu sau locație
- Filtrare după dată
- Pagina de detalii eveniment
- Imagine eveniment, locație, descriere, perioadă

### 🎫 Bilete
- Tipuri multiple de bilete per eveniment
- Stoc limitat
- Rezervare atomică (transaction safe)
- Anulare rezervare dacă nu este plătită
- Vizualizare bilete plătite

### 💳 Plăți (Stripe)
- Stripe Payment Intent
- Confirmare automată plată
- Webhook Stripe
- Gestionare status plată

### 🧑‍💼 Organizatori
- Creare / editare evenimente
- Gestionare bilete
- Vizualizare rezervări
- Dashboard „My Events”

---

## 🛠️ Tehnologii utilizate

- Python 3
- Django
- Stripe API
- SQLite / PostgreSQL
- HTML, CSS, Bootstrap
- JavaScript

---

## ⚙️ Instalare locală

### 1️⃣ Clonează repository-ul
```bash
git clone https://github.com/username/event-ticketing-platform.git
cd event-ticketing-platform
```

### 2️⃣ Creează un virtual environment
```bash
python -m venv venv
source venv/bin/activate   # Linux / Mac
venv\Scripts\activate    # Windows
```

### 3️⃣ Instalează dependențele
```bash
pip install -r requirements.txt
```

### 4️⃣ Configurează variabilele Stripe

În `settings.py`:
```python
STRIPE_PUBLIC_KEY = "pk_test_..."
STRIPE_SECRET_KEY = "sk_test_..."
STRIPE_WEBHOOK_SECRET = "whsec_..."
STRIPE_CURRENCY = "eur"
```

---

### 5️⃣ Migrații și rulare server
```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Accesează aplicația la:
```
http://127.0.0.1:8000/
```

---

## 🔐 Stripe Webhook (local)

Pentru testare locală:
```bash
stripe listen --forward-to localhost:8000/stripe/webhook/
```

---

## 📌 Posibile îmbunătățiri
- Trimitere email de confirmare
- QR code pe bilete
- Refund-uri Stripe
- REST API cu Django Rest Framework
- Admin dashboard avansat

---

## 👨‍💻 Autor

Proiect realizat cu ❤️ folosind **Django & Stripe**  
Potrivit pentru **portofoliu / licență / internship**

---

## 📜 Licență

MIT License
