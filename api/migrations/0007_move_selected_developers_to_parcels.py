# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.contrib.postgres.fields
from django.db import migrations, models


def forwards_func(apps, schema_editor):
    Parcel = apps.get_model("api", "Parcel")
    db_alias = schema_editor.connection.alias

    parcels = Parcel.objects.using(db_alias).all()

    for parcel in parcels:
        parcel.selected_developers = parcel.property_manager.selected_developers
        parcel.save()


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0006_make_parcel_id_manager_id_unique_together'),
    ]

    operations = [
        migrations.AddField(
            model_name='parcel',
            name='selected_developers',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), default=[], size=None),
        ),
        migrations.RunPython(forwards_func),
        migrations.RemoveField(
            model_name='propertymanager',
            name='selected_developers',
        ),
    ]
