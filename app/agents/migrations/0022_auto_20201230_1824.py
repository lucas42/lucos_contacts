# Generated by Django 3.1.4 on 2020-12-30 18:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0021_auto_20201005_1518'),
    ]

    operations = [
        migrations.AlterField(
            model_name='relationship',
            name='relationshipType',
            field=models.CharField(choices=[('child', 'Páiste'), ('parent', 'Tuismitheoir'), ('sibling', 'Siblín'), ('half-sibling', 'Leath-Siblín'), ('grandchild', 'Garpháiste'), ('grandparent', 'Seantuismitheoir'), ('aunt/uncle', 'Aunt/Uncle'), ('nibling', 'Niblín'), ('great aunt/uncle', 'Great Aunt/Uncle'), ('great nibling', 'Great Nibling'), ('first cousin', 'Col Ceathrair')], max_length=127),
        ),
    ]