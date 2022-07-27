# Generated by Django 3.2.14 on 2022-07-09 19:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0029_alter_facebookaccount_userid'),
    ]

    operations = [
        migrations.AlterField(
            model_name='relationship',
            name='relationshipType',
            field=models.CharField(choices=[('child', 'Páiste'), ('parent', 'Tuismitheoir'), ('sibling', 'Siblín'), ('half-sibling', 'Leath-Siblín'), ('grandchild', 'Garpháiste'), ('grandparent', 'Seantuismitheoir'), ('aunt/uncle', 'Aunt/Uncle'), ('nibling', 'Niblín'), ('first cousin', 'Col Ceathrair'), ('great aunt/uncle', 'Great Aunt/Uncle'), ('great nibling', 'Garniblín')], max_length=127),
        ),
    ]