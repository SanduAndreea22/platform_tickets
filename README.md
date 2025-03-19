# 🎟️ Platformă de Vânzare Bilete

## 📌 Descriere
Această platformă permite utilizatorilor să descopere, filtreze și cumpere bilete pentru diverse evenimente, iar administratorii pot gestiona evenimentele și vânzările.

## 🚀 Funcționalități

### 🌍 Pagini pentru Utilizatori
- **🏠 Pagină Home** – Prezentare generală a platformei și evenimente recomandate.
- **📅 Listă Evenimente** – Afișează toate evenimentele disponibile, cu filtre (categorie, dată, locație).
- **📌 Detalii Eveniment** – Pagină individuală pentru fiecare eveniment cu descriere, locație, preț bilete, recenzii.
- **🎟️ Cumpărare Bilete** – Selectare bilete, introducere detalii și plată prin Stripe, PayPal sau Revolut.
- **🔍 Căutare și Filtrare Evenimente** – Permite utilizatorilor să caute evenimente după oraș, dată, categorie.

### 🔒 Pagini pentru Admin
- **Dashboard Admin** – Vizualizarea tuturor evenimentelor create.
- **Creare Eveniment** – Formular pentru adăugarea unui nou eveniment.
- **Editare Eveniment** – Modificarea detaliilor unui eveniment existent.
- **Personalizare Eveniment** – Alegerea temei, decorurilor și playlistului.
- **Vânzare de Bilete & Check-in** – Setarea prețurilor, opțiuni de discount, gestionarea biletelor.

## 🛠️ Tehnologii Utilizate
- **Backend:** Django (Python)
- **Frontend:** HTML, CSS, Bootstrap
- **Bază de date:** PostgreSQL / SQLite
- **Plăți online:** Stripe, PayPal, Revolut
- **Autentificare:** Django Authentication, JWT

## ⚙️ Instalare și Configurare
1. **Clonează repository-ul:**
   ```bash
   git clone https://github.com/user/repo-name.git
   cd repo-name
   ```
2. **Activează un mediu virtual:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Pentru macOS/Linux
   venv\Scripts\activate  # Pentru Windows
   ```
3. **Instalează dependențele:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Aplică migrațiile bazei de date:**
   ```bash
   python manage.py migrate
   ```
5. **Rulează serverul local:**
   ```bash
   python manage.py runserver
   ```


## 🤝 Contribuții
Oricine dorește să contribuie la acest proiect este binevenit! Te rugăm să deschizi un issue sau un pull request.



