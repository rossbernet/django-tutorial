from django.conf import settings
from django.db import transaction
from django.core.validators import URLValidator
from django.contrib.auth.forms import PasswordResetForm
from rest_framework.serializers import (CharField, ModelSerializer,
                                        ValidationError, SerializerMethodField,
                                        BooleanField, EmailField)
from rest_auth.serializers import (PasswordResetSerializer,
                                   PasswordResetConfirmSerializer)

from api.models import PropertyManager, User, Parcel
from api.libs import email_property_manager, email_selected_developers
from api.errors import ParcelsAlreadySubmitted


def is_interested_in_gsi(gsi_type, property_manager):
    return any({
        gsi for gsi
        in Parcel.objects
                 .filter(property_manager=property_manager)
                 .values_list(gsi_type, flat=True)
    })


class CreatePropertyManagerSerializer(ModelSerializer):
    class Meta:
        model = PropertyManager
        exclude = ('created_at', 'updated_at')
        extra_kwargs = {'selected_developers': {'read_only': False,
                                                'required': False}}

    def validate(self, data):
        if not ("email" in data):
            raise ValidationError("email is required")

        return data

    @transaction.atomic
    def create(self, validated_data):
        parcels = self.initial_data.get('parcels', [])
        selected_developers = self.initial_data.get('selected_developers', [])
        green_roof = self.initial_data.get('green_roof', False)
        subsurface_storage = self.initial_data.get('subsurface_storage', False)
        cistern = self.initial_data.get('cistern', False)
        permeable_pavement = self.initial_data.get('permeable_pavement', False)
        rain_garden = self.initial_data.get('rain_garden', False)
        note = self.initial_data.get('note', '')
        manager = PropertyManager.objects.create(**validated_data)

        existing_parcels = []

        for parcel in parcels:
            if Parcel.objects.filter(parcel_id=parcel['id']).exists():
                existing_parcels.append(parcel)
            else:
                Parcel.objects.create(parcel_id=parcel['id'],
                                      address=parcel['address'],
                                      building_type=parcel['building_type'],
                                      property_manager=manager,
                                      selected_developers=selected_developers,
                                      rain_garden=rain_garden,
                                      cistern=cistern,
                                      subsurface_storage=subsurface_storage,
                                      permeable_pavement=permeable_pavement,
                                      green_roof=green_roof,
                                      note=note)

        if (len(existing_parcels)):
            raise ParcelsAlreadySubmitted({
                "parcels":
                    [
                        "Parcel at {} already submitted".format(p["address"])
                        for p in existing_parcels
                    ]
                }, code=400)

        parcel_ids = [parcel['id'] for parcel in parcels]
        email_property_manager(manager, note, selected_developers, parcel_ids)
        email_selected_developers(manager, note, parcel_ids)

        return manager


class PropertyManagerSerializer(ModelSerializer):
    parcels = SerializerMethodField()
    rain_garden = SerializerMethodField()
    green_roof = SerializerMethodField()
    subsurface_storage = SerializerMethodField()
    permeable_pavement = SerializerMethodField()
    cistern = SerializerMethodField()
    note = SerializerMethodField()
    selected_developers = SerializerMethodField()

    def get_parcels(self, property_manager):
        return [
            {
                "id": id,
                "parcel_id": parcel_id,
                "address": parcel_address,
                "building_type": parcel_building_type,
            } for (id, parcel_id, parcel_address, parcel_building_type)
            in Parcel.objects
                     .filter(property_manager=property_manager)
                     .values_list('id', 'parcel_id', 'address',
                                  'building_type')
        ]

    def get_rain_garden(self, property_manager):
        return is_interested_in_gsi('rain_garden', property_manager)

    def get_green_roof(self, property_manager):
        return is_interested_in_gsi('green_roof', property_manager)

    def get_subsurface_storage(self, property_manager):
        return is_interested_in_gsi('subsurface_storage', property_manager)

    def get_permeable_pavement(self, property_manager):
        return is_interested_in_gsi('permeable_pavement', property_manager)

    def get_cistern(self, property_manager):
        return is_interested_in_gsi('cistern', property_manager)

    def get_note(self, property_manager):
        return "; ".join({
            note for note
            in Parcel.objects
                     .filter(property_manager=property_manager)
                     .values_list('note', flat=True)
        })

    def get_selected_developers(self, property_manager):
        return list({
            developer for selected_developers
            in Parcel.objects
                     .filter(property_manager=property_manager)
                     .values_list('selected_developers', flat=True)
            for developer in selected_developers
        })

    class Meta:
        model = PropertyManager
        fields = ('id', 'name', 'email', 'phone', 'note', 'prefer_email',
                  'prefer_phone', 'rain_garden', 'subsurface_storage',
                  'green_roof', 'cistern', 'permeable_pavement', 'parcels',
                  'selected_developers', 'created_at')


class ParcelSerializer(ModelSerializer):
    class Meta:
        model = Parcel
        exclude = ('created_at', 'updated_at')


class UserSerializer(ModelSerializer):
    password = CharField(write_only=True)
    is_email_verified = BooleanField(read_only=True)

    def validate_company_website(self, url):
        if not url:
            return url

        if '://' not in url:
            url = 'http://{}'.format(url)

        message = 'URL must begin with http:// or https://'
        validate = URLValidator(schemes=['http', 'https'], message=message)

        validate(url)

        return url

    class Meta:
        model = User
        exclude = ()

    def create(self, validated_data):
        user = super(UserSerializer, self).create(validated_data)
        user.set_password(validated_data['password'])
        user.save()
        return user


class RetrofitDeveloperInfoSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'company_name', 'company_phone', 'company_email',
                  'company_website', 'rain_garden', 'subsurface_storage',
                  'green_roof', 'permeable_pavement', 'cistern',
                  'has_grant_approval', 'other_retrofit', 'is_design_firm',
                  'is_construction_firm', 'is_maintenance_firm')


class DeveloperPasswordResetSerializer(PasswordResetSerializer):
    email = EmailField()

    password_reset_form_class = PasswordResetForm

    def validate_email(self, value):
        # Create PasswordResetForm with the serializer
        data = self.initial_data
        self.reset_form = self.password_reset_form_class(data=data)
        if not self.reset_form.is_valid():
            raise ValidationError("Error")

        if not User.objects.filter(email=value).exists():
            raise ValidationError("Invalid e-mail address")

        return value

    def save(self):
        request = self.context.get('request')
        # Set some values to trigger the send_email method.
        opts = {
            'use_https': request.is_secure(),
            'domain_override': getattr(settings, 'RETROFIT_MAP_URL'),
            'from_email': getattr(settings, 'DEFAULT_FROM_EMAIL'),
            'request': request,
            'subject_template_name':
                'mail/reset_developer_password_subject.txt',
            'email_template_name':
                'mail/reset_developer_password_body.txt',
            'html_email_template_name':
                'mail/reset_developer_password_body.html',
        }

        self.reset_form.save(**opts)


class DeveloperPasswordResetConfirmSerializer(PasswordResetConfirmSerializer):
    @transaction.atomic
    def save(self):
        self.user.has_admin_generated_password = False
        self.user.save()

        return self.set_password_form.save()
