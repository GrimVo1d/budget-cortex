from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ledger', '0004_transaction_brin_occurred_at'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='category',
            constraint=models.UniqueConstraint(condition=models.Q(('is_deleted', False), ('parent__isnull', True)), fields=('user', 'name'), name='category_unique_alive_root'),
        ),
    ]
