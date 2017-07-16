# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2017-07-16 13:43
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0002_phone_postal'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Phone',
            new_name='PhoneNumber',
        ),
        migrations.RenameModel(
            old_name='Postal',
            new_name='PostalAddress',
        ),
        migrations.AlterModelOptions(
            name='postaladdress',
            options={'verbose_name_plural': 'Postal Addresses'},
        ),
    ]
