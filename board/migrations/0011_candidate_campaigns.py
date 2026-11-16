from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('board', '0010_merge_employer_submission_admin_sections')]
    operations = [
        migrations.AddField(model_name='jobseeker', name='marketing_consent',
                            field=models.BooleanField(default=False)),
        migrations.CreateModel(
            name='CandidateCampaign',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('audience', models.CharField(choices=[
                    ('all', 'All opted-in candidates'), ('jobseekers', 'Canadian job board candidates'),
                    ('international', 'International planner candidates')], default='all', max_length=20)),
                ('subject', models.CharField(max_length=200)),
                ('body', models.TextField()),
                ('queued_at', models.DateTimeField(blank=True, editable=False, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['-created_at', '-pk']},
        ),
        migrations.CreateModel(
            name='CandidateCampaignDelivery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=254)),
                ('status', models.CharField(choices=[
                    ('pending', 'Pending'), ('sending', 'Sending'), ('sent', 'Sent'),
                    ('failed', 'Failed'), ('skipped', 'No longer eligible')], default='pending', max_length=12)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name='deliveries', to='board.candidatecampaign')),
            ],
            options={'constraints': [models.UniqueConstraint(
                fields=('campaign', 'email'), name='unique_candidate_campaign_email')]},
        ),
    ]
