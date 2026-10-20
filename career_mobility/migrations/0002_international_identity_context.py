from django.db import migrations, models
class Migration(migrations.Migration):
 dependencies=[('career_mobility','0001_initial')]
 operations=[
 migrations.AddField(model_name='internationalprofile',name='citizenship_country',field=models.CharField(max_length=100,blank=True)),
 migrations.AddField(model_name='internationalprofile',name='residence_country',field=models.CharField(max_length=100,blank=True)),
 migrations.AddField(model_name='internationalprofile',name='canadian_immigration_status',field=models.CharField(max_length=40,blank=True)),
 migrations.AddField(model_name='internationalprofile',name='graduation_year',field=models.PositiveSmallIntegerField(null=True,blank=True)),
 migrations.AddField(model_name='internationalprofile',name='registered_in_education_country',field=models.CharField(max_length=15,blank=True)),
 ]
