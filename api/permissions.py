from django.core.exceptions import (ObjectDoesNotExist)
from rest_framework import permissions

from api.models import User


class IsPwdStaff(permissions.BasePermission):
    """
    Check if a user is PWD Staff
    """

    def has_permission(self, request, view, email=None):
        if not email:
            email = request.user
        try:
            User.objects.exclude(is_staff=False).get(email=email)
            return True
        except ObjectDoesNotExist:
            return False
