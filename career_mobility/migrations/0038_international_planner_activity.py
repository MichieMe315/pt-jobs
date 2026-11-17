from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('career_mobility', '0037_digitalproduct_starter_quantity_and_more')]

    operations = [
        migrations.AddField(
            model_name='internationalactivity',
            name='destination_province',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AlterField(
            model_name='internationalactivity',
            name='action',
            field=models.CharField(max_length=32, choices=[
                ('account_created', 'Account created'),
                ('signed_in', 'Signed in'),
                ('signed_out', 'Signed out'),
                ('planner_viewed', 'Planner viewed'),
                ('planner_generated', 'Planner generated'),
                ('planner_saved', 'Planner saved'),
                ('country_viewed', 'Country viewed'),
                ('resources_viewed', 'Resources viewed'),
                ('dashboard_viewed', 'Dashboard viewed'),
                ('profile_updated', 'Profile updated'),
                ('checklist_completed', 'Checklist completed'),
                ('checklist_reopened', 'Checklist reopened'),
                ('checklist_downloaded', 'Checklist downloaded'),
                ('country_guide_downloaded', 'Country guide downloaded'),
                ('checkout_started', 'Checkout started'),
                ('purchase_confirmed', 'Purchase confirmed'),
                ('product_downloaded', 'Product downloaded'),
            ]),
        ),
    ]
