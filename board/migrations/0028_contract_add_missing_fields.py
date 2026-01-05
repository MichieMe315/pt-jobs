# board/migrations/0028_contract_add_missing_fields.py
from django.db import migrations, models
import django.db.models.deletion


def copy_slug_to_key(apps, schema_editor):
    EmailTemplate = apps.get_model('board', 'EmailTemplate')
    # If existing rows have empty key, copy slug -> key
    for et in EmailTemplate.objects.all().iterator():
        key = getattr(et, 'key', '')
        slug = getattr(et, 'slug', '')
        if not key:
            et.key = slug or f"email-{et.pk}"
            et.save(update_fields=['key'])


class Migration(migrations.Migration):

    dependencies = [
        ('board', '0027_add_created_at_to_discountcode'),
    ]

    operations = [
        # --- SiteSettings (add the fields your admin & base.html expect) ---
        migrations.AddField(
            model_name='sitesettings',
            name='google_analytics_id',
            field=models.CharField(max_length=64, blank=True, default=''),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='seo_meta_title',
            field=models.CharField(max_length=255, blank=True, default=''),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='seo_meta_description',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='share_facebook',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='share_instagram',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='share_reddit',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='side_banner_html',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='bottom_banner_html',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='mapbox_token',
            field=models.CharField(max_length=255, blank=True, default=''),
        ),

        # --- PostingPackage (admin/product controls you requested) ---
        migrations.AddField(
            model_name='postingpackage',
            name='featured_employer',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='postingpackage',
            name='featured_job',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='postingpackage',
            name='product_expires_days',
            field=models.PositiveIntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='postingpackage',
            name='available_from',
            field=models.DateField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='postingpackage',
            name='available_to',
            field=models.DateField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='postingpackage',
            name='is_trial',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='postingpackage',
            name='assign_on_signup',
            field=models.BooleanField(default=False),
        ),

        # --- DiscountCode (package scoping & caps) ---
        migrations.AddField(
            model_name='discountcode',
            name='applies_to_package',
            field=models.ForeignKey(
                to='board.postingpackage',
                on_delete=django.db.models.deletion.SET_NULL,
                null=True, blank=True, related_name='discount_codes'
            ),
        ),
        migrations.AddField(
            model_name='discountcode',
            name='max_uses_per_user',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='discountcode',
            name='max_uses_total',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='discountcode',
            name='active',
            field=models.BooleanField(default=True),
        ),

        # --- EmailTemplate (key used by code) ---
        migrations.AddField(
            model_name='emailtemplate',
            name='key',
            field=models.CharField(max_length=255, blank=True, default=''),
        ),
        migrations.RunPython(copy_slug_to_key, migrations.RunPython.noop),

        # --- Invoice (amount/currency/gateway/status/external_id) ---
        migrations.AddField(
            model_name='invoice',
            name='amount',
            field=models.DecimalField(max_digits=10, decimal_places=2, default=0),
        ),
        migrations.AddField(
            model_name='invoice',
            name='currency',
            field=models.CharField(max_length=8, default='CAD'),
        ),
        migrations.AddField(
            model_name='invoice',
            name='gateway',
            field=models.CharField(max_length=16, default='admin'),
        ),
        migrations.AddField(
            model_name='invoice',
            name='external_id',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='status',
            field=models.CharField(max_length=32, default='paid'),
        ),
    ]
