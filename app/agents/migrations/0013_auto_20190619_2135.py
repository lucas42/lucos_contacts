# -*- coding: utf-8 -*-
# Generated by Django 1.11.21 on 2019-06-19 21:35
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0011_auto_20190616_2033'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='account',
            name='agent',
        ),
        migrations.RemoveField(
            model_name='account',
            name='type',
        ),
        migrations.DeleteModel(
            name='Account',
        ),
        migrations.DeleteModel(
            name='AccountType',
        ),
    ]
