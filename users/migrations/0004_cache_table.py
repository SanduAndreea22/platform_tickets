from django.db import migrations
from django.core.management import call_command


def create_cache_table(apps, schema_editor):
    call_command("createcachetable", "django_cache_table")


def drop_cache_table(apps, schema_editor):
    schema_editor.execute("DROP TABLE IF EXISTS django_cache_table")


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_alter_customuser_options"),
    ]

    operations = [
        migrations.RunPython(create_cache_table, drop_cache_table),
    ]
