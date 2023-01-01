# Generated by Django 3.2.16 on 2023-01-01 22:02

from django.db import migrations, models
import django.db.models.functions.text


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0038_romanticrelationship'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='relationship',
            options={'ordering': [django.db.models.functions.text.Lower('subject___name')]},
        ),
        migrations.AlterField(
            model_name='romanticrelationship',
            name='milestone',
            field=models.CharField(choices=[('dating', 'Dating'), ('cohabitation', 'Cohabitation'), ('engaged', 'Engaged'), ('married', 'Married')], default='dating', max_length=127),
        ),
    ]
