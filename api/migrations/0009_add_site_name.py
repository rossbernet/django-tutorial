# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from django.contrib.sites.models import Site
from django.conf import settings

def forwards_func(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    site, _ = Site.objects.using(db_alias).get_or_create(id=settings.SITE_ID)
    site.domain = 'pwd.garp.com'
    site.name = 'PWD GARP'
    site.save()


class Migration(migrations.Migration):

    dependencies = [
        ('sites', '0002_alter_domain_unique'),
        ('api', '0008_move_retrofits_to_parcels'),
    ]

    operations = [
        migrations.RunPython(forwards_func),
    ]
