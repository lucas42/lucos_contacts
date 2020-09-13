# Generated by Django 3.1 on 2020-09-13 15:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0018_auto_20200907_0054'),
    ]

    operations = [
        migrations.AlterField(
            model_name='relationship',
            name='relationshipType',
            field=models.CharField(choices=[('child', 'Child'), ('parent', 'Parent'), ('sibling', 'Sibling'), ('grandparent', 'Grandparent'), ('aunt/uncle', 'AuntOrUncle'), ('nibling', 'Nibling'), ('great aunt/uncle', 'GreatAuntOrGreatUncle'), ('half-sibling', 'HalfSibling')], max_length=127),
        ),
    ]
