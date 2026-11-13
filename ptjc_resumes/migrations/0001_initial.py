import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL), ('career_mobility', '0012_digitalproduct_catalogue')]
    operations = [
        migrations.CreateModel(name='ResumeTemplate', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('key', models.SlugField(default='international-professional', unique=True)),
            ('title', models.CharField(default='International physiotherapy resume', max_length=140)),
            ('is_enabled', models.BooleanField(default=False)),
            ('access_product', models.ForeignKey(help_text='The existing shop product controls price and paid access. The same purchase can include the template pack.', on_delete=django.db.models.deletion.PROTECT, to='career_mobility.digitalproduct'))]),
        migrations.CreateModel(name='ResumeDraft', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('title', models.CharField(default='My international resume', max_length=120)),
            ('data', models.JSONField(default=dict)), ('revision', models.PositiveIntegerField(default=1)),
            ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
            ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='private_resume_drafts', to=settings.AUTH_USER_MODEL)),
            ('template', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='ptjc_resumes.resumetemplate'))], options={'ordering': ['-updated_at']})]
