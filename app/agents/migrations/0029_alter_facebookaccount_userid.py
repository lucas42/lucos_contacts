# Generated by Django 3.2.6 on 2021-10-19 23:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0028_alter_agent__name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='facebookaccount',
            name='userid',
            field=models.PositiveBigIntegerField(),
        ),
    ]
