import uuid
from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from allauth.account.models import EmailAddress


class EmailAsUsernameUserManager(BaseUserManager):
    """
    A custom user manager to deal with emails as unique identifiers for auth
    instead of usernames. The default that's used is "UserManager"
    """
    def _create_user(self, email, password, **extra_fields):
        """
        Creates and saves a User with the given email and password.
        """
        if not email:
            raise ValueError('The Email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self._create_user(email, password, **extra_fields)


class PropertyManager(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=60, null=False, blank=False)
    email = models.EmailField(null=False, blank=False, unique=True)
    phone = models.CharField(max_length=20, blank=True)
    prefer_email = models.BooleanField(default=False)
    prefer_phone = models.BooleanField(default=False)
    unsubscribe_token = models.UUIDField(editable=False, default=uuid.uuid4,
                                         unique=True)


class Parcel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    parcel_id = models.IntegerField(null=False, blank=False, unique=True)
    property_manager = models.ForeignKey(PropertyManager,
                                         related_name='parcels',
                                         on_delete=models.CASCADE)
    address = models.CharField(max_length=60, blank=True)
    building_type = models.CharField(max_length=60, blank=True)
    selected_developers = ArrayField(models.IntegerField(), default=[])
    rain_garden = models.BooleanField(default=False)
    subsurface_storage = models.BooleanField(default=False)
    green_roof = models.BooleanField(default=False)
    permeable_pavement = models.BooleanField(default=False)
    cistern = models.BooleanField(default=False)
    note = models.TextField(blank=True)
    accepts_contacts = models.BooleanField(default=True)

    class Meta:
        unique_together = ('parcel_id', 'property_manager')


class User(AbstractBaseUser, PermissionsMixin):
    USERNAME_FIELD = 'email'
    objects = EmailAsUsernameUserManager()

    STATUS_PENDING = 0
    STATUS_DENIED = 1
    STATUS_ACTIVE = 2
    STATUS_DEACTIVATED = 3

    USER_STATUSES = (
        (STATUS_PENDING, 'pending'),
        (STATUS_DENIED, 'denied'),
        (STATUS_ACTIVE, 'active'),
        (STATUS_DEACTIVATED, 'deactivated'),
    )

    is_staff = models.BooleanField(
        ('staff status'),
        default=False,
        help_text=('Designates whether the user can log into this site.'),
    )
    is_active = models.BooleanField(
        ('active'),
        default=True,
        help_text=(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'
        ),
    )

    email = models.EmailField(unique=True, null=False)
    username = models.CharField(max_length=20, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True)
    deactivated_at = models.DateTimeField(null=True)
    denied_at = models.DateTimeField(null=True)
    status = models.IntegerField(choices=USER_STATUSES, default=0)
    name = models.CharField(max_length=60, null=False, blank=False)
    phone = models.CharField(max_length=20, blank=True)
    company_name = models.CharField(max_length=100, null=False, blank=False)
    company_email = models.EmailField(blank=False)
    company_phone = models.CharField(max_length=20, null=False, blank=False)
    company_website = models.CharField(max_length=100, blank=True)
    rain_garden = models.BooleanField(default=False)
    subsurface_storage = models.BooleanField(default=False)
    green_roof = models.BooleanField(default=False)
    permeable_pavement = models.BooleanField(default=False)
    cistern = models.BooleanField(default=False)
    other_retrofit = models.CharField(max_length=60, blank=True)
    ein = models.CharField(max_length=20, null=False, blank=False)
    commercial_activity_license = models.CharField(max_length=20, blank=True)
    should_email_parcel_updates_preference = models.BooleanField(default=False)
    saved_parcel_ids = ArrayField(models.IntegerField(), null=False,
                                  default=list)
    has_grant_approval = models.BooleanField(default=False)
    has_admin_generated_password = models.BooleanField(default=False)
    reason_for_denial = models.TextField(blank=True, default='', null=False)
    is_design_firm = models.BooleanField(default=False)
    is_construction_firm = models.BooleanField(default=False)
    is_maintenance_firm = models.BooleanField(default=False)

    def __str__(self):
        return self.email

    def get_full_name(self):
        return self.email

    def get_short_name(self):
        return self.email

    def first_name(self):
        return self.email

    def last_name(self):
        pass

    @property
    def interested(self):
        return [
            {
                "parcel_id": parcel.parcel_id,
                "address": parcel.address,
                "contact_name": parcel.property_manager.name,
                "contact_email": parcel.property_manager.email
                if parcel.property_manager.prefer_email else None,
                "contact_phone": parcel.property_manager.phone
                if parcel.property_manager.prefer_phone else None,
                "retrofits": {
                    "rain_garden": parcel.rain_garden,
                    "subsurface_storage": parcel.subsurface_storage,
                    "permeable_pavement": parcel.permeable_pavement,
                    "green_roof": parcel.green_roof,
                    "cistern": parcel.cistern,
                },
                "note": parcel.note,
            } for parcel
            in Parcel.objects
                     .filter(selected_developers__contains=[self.id])
        ]

    @property
    def enrolled(self):
        return [
            {
                "parcel_id": parcel.parcel_id,
                "accepts_contacts": parcel.accepts_contacts
            } for parcel
            in Parcel.objects.all()
        ]

    @property
    def is_email_verified(self):
        email_address = EmailAddress.objects.get_primary(self.id)
        if email_address:
            return email_address.verified
        return False
