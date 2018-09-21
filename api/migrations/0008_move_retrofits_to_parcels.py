# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def forwards_func(apps, schema_editor):
    Parcel = apps.get_model("api", "Parcel")
    db_alias = schema_editor.connection.alias

    parcels = Parcel.objects.using(db_alias).all()

    for parcel in parcels:
        parcel.rain_garden = parcel.property_manager.rain_garden
        parcel.cistern = parcel.property_manager.cistern
        parcel.green_roof = parcel.property_manager.green_roof
        parcel.subsurface_storage = parcel.property_manager.subsurface_storage
        parcel.stormwater_basin = parcel.property_manager.stormwater_basin
        parcel.permeable_pavement = parcel.property_manager.permeable_pavement
        parcel.note = parcel.property_manager.note
        parcel.save()


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0007_move_selected_developers_to_parcels'),
    ]

    operations = [
        migrations.AddField(
            model_name='parcel',
            name='green_roof',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='parcel',
            name='permeable_pavement',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='parcel',
            name='rain_garden',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='parcel',
            name='stormwater_basin',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='parcel',
            name='subsurface_storage',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='parcel',
            name='cistern',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='parcel',
            name='note',
            field=models.TextField(blank=True),
        ),
        migrations.RunPython(forwards_func),
        migrations.RemoveField(
            model_name='propertymanager',
            name='cistern',
        ),
        migrations.RemoveField(
            model_name='propertymanager',
            name='green_roof',
        ),
        migrations.RemoveField(
            model_name='propertymanager',
            name='permeable_pavement',
        ),
        migrations.RemoveField(
            model_name='propertymanager',
            name='rain_garden',
        ),
        migrations.RemoveField(
            model_name='propertymanager',
            name='stormwater_basin',
        ),
        migrations.RemoveField(
            model_name='propertymanager',
            name='subsurface_storage',
        ),
        migrations.RemoveField(
            model_name='propertymanager',
            name='note',
        ),
        migrations.AlterField(
            model_name='parcel',
            name='parcel_id',
            field=models.IntegerField(unique=True),
        ),
    ]
