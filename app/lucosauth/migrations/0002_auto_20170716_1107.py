# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2017-07-16 11:07
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lucosauth', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lucosuser',
            name='last_login',
            field=models.DateTimeField(blank=True, null=True, verbose_name='last login'),
        ),
    ]