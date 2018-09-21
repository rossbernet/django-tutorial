from __future__ import unicode_literals

from django.contrib.sites.shortcuts import get_current_site
from django.conf import settings
from allauth.account.adapter import DefaultAccountAdapter
from allauth.utils import build_absolute_uri

from api.models import User


class RetrofitDeveloperAccountAdapter(DefaultAccountAdapter):
    def get_from_email(self):
        return settings.DEFAULT_FROM_EMAIL

    def get_email_confirmation_url(self, request, emailconfirmation):
        uri = '/email-confirmation/' + emailconfirmation.key
        return build_absolute_uri(request, uri)

    def send_confirmation_mail(self, request, emailconfirmation, signup):
        current_site = get_current_site(request)
        activate_url = self.get_email_confirmation_url(
            request,
            emailconfirmation)
        user_id = emailconfirmation.email_address.user_id
        name = User.objects.get(id=user_id).name
        ctx = {
            "name": name,
            "activate_url": activate_url,
            "current_site": current_site,
            "key": emailconfirmation.key,
        }
        email_template = 'mail/email_confirmation'
        self.send_mail(email_template,
                       emailconfirmation.email_address.email,
                       ctx)
