# -*- coding: utf-8 -*-
# Generated by Django 1.11.21 on 2019-06-16 20:31
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0009_emailaddress_googleaccount_googlecontact'),
    ]

    operations = [
        migrations.AlterField(
            model_name='emailaddress',
            name='address',
            field=models.EmailField(max_length=255),
        ),
        migrations.AlterField(
            model_name='facebookaccount',
            name='userid',
            field=models.BigIntegerField(),
        ),
        migrations.AlterField(
            model_name='googleaccount',
            name='userid',
            field=models.BigIntegerField(),
        ),
    ]