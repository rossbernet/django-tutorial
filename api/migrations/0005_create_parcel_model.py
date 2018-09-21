# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


def forwards_func(apps, schema_editor):
    PropertyManager = apps.get_model("api", "PropertyManager")
    Parcel = apps.get_model("api", "Parcel")
    db_alias = schema_editor.connection.alias

    property_managers = PropertyManager.objects.using(db_alias).all()

    for manager in property_managers:
        for parcel_id in manager.parcel_ids:
            Parcel.objects.using(db_alias).create(
                parcel_id=parcel_id,
                property_manager=manager,
                accepts_contacts=manager.accepts_contacts,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0004_add_accepts_contacts_to_propertymanager'),
    ]

    operations = [
        migrations.CreateModel(
            name='Parcel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('parcel_id', models.IntegerField()),
                ('accepts_contacts', models.BooleanField(default=True)),
                ('property_manager', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='parcels', to='api.PropertyManager')),
                ('address', models.CharField(blank=True, max_length=60)),
            ],
        ),
        migrations.RunPython(forwards_func),
        migrations.RemoveField(
            model_name='propertymanager',
            name='accepts_contacts',
        ),
        migrations.RemoveField(
            model_name='propertymanager',
            name='parcel_ids',
        ),
    ]
