# -*- coding: utf-8 -*-
# Generated by Django 1.11.9 on 2018-01-16 16:06
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0005_create_parcel_model'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='parcel',
            unique_together=set([('parcel_id', 'property_manager')]),
        ),
    ]