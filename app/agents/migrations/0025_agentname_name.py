# Generated by Django 3.2.6 on 2021-09-28 16:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0024_agentname'),
    ]

    operations = [
        migrations.AddField(
            model_name='agentname',
            name='name',
            field=models.TextField(default='Unknown'),
            preserve_default=False,
        ),
    ]
