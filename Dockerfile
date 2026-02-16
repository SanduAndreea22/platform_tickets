FROM python:3.12-slim

WORKDIR /app

# Instalăm dependențele necesare sistemului
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Copiem dependențele Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiem codul sursă
COPY . .

# Colectăm fișierele statice pentru design
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Folosim Gunicorn pentru o viteză mai bună pe Render
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]