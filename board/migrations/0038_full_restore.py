# 0038_full_restore.py
# Placeholder / anchor migration so the graph is consistent again.
# It just depends on 0037 and does nothing to the DB.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0037_webhookconfig"),
    ]

    operations = []
