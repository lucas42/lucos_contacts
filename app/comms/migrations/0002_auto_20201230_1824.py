# Generated by Django 3.1.4 on 2020-12-30 18:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comms', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='christmaslist',
            name='year',
            field=models.IntegerField(editable=False, primary_key=True, serialize=False),
        ),
    ]