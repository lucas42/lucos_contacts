# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2017-07-16 11:09
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Account',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(blank=True, help_text=b'', max_length=255)),
                ('userid', models.CharField(blank=True, help_text=b'Must be unique for the given type in the given domain.  Usually persistant', max_length=255)),
                ('username', models.CharField(blank=True, help_text=b'Usually unique for the given type/domain.  Can change over time.', max_length=255)),
                ('url', models.CharField(blank=True, max_length=255)),
                ('name', models.CharField(blank=True, help_text=b'Not guaranteed to be unique.', max_length=255)),
                ('imgurl', models.CharField(blank=True, max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='AccountType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label_en', models.CharField(blank=True, max_length=255)),
                ('label_ga', models.CharField(blank=True, max_length=255)),
                ('label_gd', models.CharField(blank=True, max_length=255)),
                ('label_cy', models.CharField(blank=True, max_length=255)),
                ('accounturi', models.CharField(blank=True, max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='Agent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name_en', models.CharField(blank=True, max_length=255)),
                ('name_ga', models.CharField(blank=True, max_length=255)),
                ('name_gd', models.CharField(blank=True, max_length=255)),
                ('name_cy', models.CharField(blank=True, max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='ExternalAgent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('agent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='agents.Agent')),
            ],
        ),
        migrations.CreateModel(
            name='Relationship',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='object', to='agents.Agent')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subject', to='agents.Agent')),
            ],
        ),
        migrations.CreateModel(
            name='RelationshipType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label_en', models.CharField(blank=True, max_length=255)),
                ('label_ga', models.CharField(blank=True, max_length=255)),
                ('label_gd', models.CharField(blank=True, max_length=255)),
                ('label_cy', models.CharField(blank=True, max_length=255)),
                ('symmetrical', models.BooleanField(default=False)),
                ('transitive', models.BooleanField(default=False)),
                ('inverse', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='agents.RelationshipType')),
            ],
        ),
        migrations.CreateModel(
            name='RelationshipTypeConnection',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reversible', models.BooleanField(default=False)),
                ('inferred_relation_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inferred', to='agents.RelationshipType')),
                ('relation_type_a', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='a', to='agents.RelationshipType')),
                ('relation_type_b', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='b', to='agents.RelationshipType')),
            ],
        ),
        migrations.AddField(
            model_name='relationship',
            name='type',
            field=models.ForeignKey(help_text=b'Subject is a $type of object', on_delete=django.db.models.deletion.CASCADE, to='agents.RelationshipType'),
        ),
        migrations.AddField(
            model_name='agent',
            name='relation',
            field=models.ManyToManyField(through='agents.Relationship', to='agents.Agent'),
        ),
        migrations.AddField(
            model_name='account',
            name='agent',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='agents.Agent'),
        ),
        migrations.AddField(
            model_name='account',
            name='type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='agents.AccountType'),
        ),
    ]