# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2017-07-16 13:33
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Phone',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.PositiveIntegerField()),
                ('agent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='agents.Agent')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Postal',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('address', models.CharField(max_length=255)),
                ('agent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='agents.Agent')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
