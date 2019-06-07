# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2018-11-22 14:27
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0007_agent_gift_ideas'),
    ]

    operations = [
        migrations.AddField(
            model_name='agent',
            name='on_gift_list',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='agent',
            name='starred',
            field=models.BooleanField(default=False),
        ),
    ]