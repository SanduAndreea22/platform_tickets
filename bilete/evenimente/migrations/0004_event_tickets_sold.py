# Generated by Django 5.1.7 on 2025-03-10 17:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('evenimente', '0003_event_tickets_available'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='tickets_sold',
            field=models.IntegerField(default=0),
        ),
    ]
