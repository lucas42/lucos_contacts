# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2017-07-16 17:49
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0003_auto_20170716_1343'),
    ]

    operations = [
        migrations.CreateModel(
            name='FacebookAccount',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('userid', models.PositiveIntegerField()),
                ('username', models.CharField(blank=True, max_length=255)),
                ('agent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='agents.Agent')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
