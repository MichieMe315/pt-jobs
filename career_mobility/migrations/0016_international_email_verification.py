from django.db import migrations,models
class Migration(migrations.Migration):
    dependencies=[('career_mobility','0015_referencecost_basis_referencecost_reference_period')]
    operations=[migrations.AddField(model_name='internationalprofile',name='email_verified_address',field=models.EmailField(blank=True,editable=False,max_length=254)),migrations.AddField(model_name='internationalprofile',name='email_verified_at',field=models.DateTimeField(null=True,blank=True,editable=False)),migrations.AddField(model_name='internationalprofile',name='verification_sent_at',field=models.DateTimeField(null=True,blank=True,editable=False))]
