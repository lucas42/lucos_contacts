# Generated by Django 3.2.16 on 2022-11-12 13:45

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0033_googlephotosprofile'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='googlephotosprofile',
            name='profile_pic_url',
        ),
    ]