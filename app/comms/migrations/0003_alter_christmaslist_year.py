# Generated by Django 3.2.6 on 2021-12-19 00:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comms', '0002_auto_20201230_1824'),
    ]

    operations = [
        migrations.AlterField(
            model_name='christmaslist',
            name='year',
            field=models.IntegerField(primary_key=True, serialize=False),
        ),
    ]