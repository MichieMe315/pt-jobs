# board/migrations/0029_merge_contract_missing_fields.py
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('board', '0027_contract_add_missing_fields'),
        ('board', '0028_contract_add_missing_fields'),
    ]

    operations = []
