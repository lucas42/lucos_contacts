# Generated by Django 3.1 on 2020-08-31 17:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0014_auto_20200825_2310'),
    ]

    operations = [
        migrations.AddField(
            model_name='relationship',
            name='relationshipType',
            field=models.CharField(choices=[('child', 'Child'), ('parent', 'Parent'), ('sibling', 'Sibling')], default='missing', max_length=127),
            preserve_default=False,
        ),
    ]
