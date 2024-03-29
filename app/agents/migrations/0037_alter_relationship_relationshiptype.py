# Generated by Django 3.2.16 on 2022-12-31 01:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0036_auto_20221230_0235'),
    ]

    operations = [
        migrations.AlterField(
            model_name='relationship',
            name='relationshipType',
            field=models.CharField(choices=[('child', 'Child'), ('parent', 'Parent'), ('sibling', 'Sibling'), ('half-sibling', 'Half-Sibling'), ('grandchild', 'Grandchild'), ('grandparent', 'Grandparent'), ('aunt/uncle', 'Aunt/Uncle'), ('nibling', 'Nibling'), ('first cousin', 'Cousin'), ('great aunt/uncle', 'Great Aunt/Uncle'), ('great nibling', 'Great Nibling')], max_length=127),
        ),
    ]
