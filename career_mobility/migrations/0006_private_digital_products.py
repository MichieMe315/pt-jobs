from django.db import migrations, models
import career_mobility.private_storage
class Migration(migrations.Migration):
    dependencies=[("career_mobility","0005_career_tools_integrated")]
    operations=[migrations.AlterField(model_name="digitalproduct",name="download",field=models.FileField(blank=True,storage=career_mobility.private_storage.PrivateMobilityStorage(),upload_to="career_mobility/products/"))]
