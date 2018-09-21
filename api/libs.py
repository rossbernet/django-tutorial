from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import get_template

from api.models import User, Parcel


def format_selected_retrofits(obj):
    return ", ".join([
        retrofit for retrofit, selected
        in {
            'Rain Garden': obj.rain_garden,
            'Subsurface Storage': obj.subsurface_storage,
            'Green Roof': obj.green_roof,
            'Permeable Pavement': obj.permeable_pavement,
            'Cistern': obj.cistern,
        }.items() if selected
    ])


def format_developer_for_manager_email(id):
    developer = User.objects.get(id=id)

    return {
        'company_name': developer.company_name,
        'company_email': developer.company_email,
        'company_phone': developer.company_phone,
        'company_address': '990 S Garden' if id % 2 == 0 else '1234 Market',
        'company_website': developer.company_website,
        'specialties': format_selected_retrofits(developer),
    }


def email_property_manager(manager, note, selected_developer_ids, parcel_ids):
    subject_template = get_template('mail/manager_confirmation_subject.txt')
    text_template = get_template('mail/manager_confirmation_body.txt')
    html_template = get_template('mail/manager_confirmation_body.html')

    subject_dict = {
        'name': manager.name,
    }

    preferred_contact = 'Email'
    if (manager.prefer_email and manager.prefer_phone):
        preferred_contact = 'Doesn\'t matter'
    elif manager.prefer_phone:
        preferred_contact = 'Phone'

    selected_developers = [
        format_developer_for_manager_email(id)
        for id in selected_developer_ids
    ]

    unsubscribe_url = "{}/preferences?token={}".format(
        settings.MARKETING_EMAIL_OPT_OUT_URL,
        manager.unsubscribe_token)

    parcels_qs = Parcel.objects \
                       .filter(property_manager=manager) \
                       .filter(parcel_id__in=parcel_ids)

    parcel_addresses = ", ".join([
        address for address
        in parcels_qs.values_list('address', flat=True)
    ])

    selected_retrofits = format_selected_retrofits(parcels_qs.first()) \
        if parcels_qs else []

    body_dict = {
        'name': manager.name,
        'email': manager.email,
        'phone': manager.phone,
        'preferred_contact': preferred_contact,
        'note': note,
        'parcels': parcel_addresses,
        'selected_developers': selected_developers,
        'selected_retrofits': selected_retrofits,
        'unsubscribe_url': unsubscribe_url,
    }

    subject_text = subject_template.render(subject_dict).rstrip()
    body_text = text_template.render(body_dict)
    body_html = html_template.render(body_dict)

    send_mail(
        subject_text,
        body_text,
        settings.DEFAULT_FROM_EMAIL,
        [manager.email],
        html_message=body_html,
    )


def send_property_manager_preferences_email(parcel):
    subject_template = get_template('mail/manager_preferences_subject.txt')
    text_template = get_template('mail/manager_preferences_body.txt')
    html_template = get_template('mail/manager_preferences_body.html')

    manager = parcel.property_manager

    subject_dict = {
        'name': manager.name
    }

    preferences_url = "{}/preferences?token={}".format(
        settings.MARKETING_EMAIL_OPT_OUT_URL,
        manager.unsubscribe_token)

    body_dict = {
        'name': manager.name,
        'preferences_url': preferences_url
    }

    subject_text = subject_template.render(subject_dict).rstrip()
    body_text = text_template.render(body_dict)
    body_html = html_template.render(body_dict)

    send_mail(
        subject_text,
        body_text,
        settings.DEFAULT_FROM_EMAIL,
        [manager.email],
        html_message=body_html,
    )


def create_property_url(parcel):
    return "{}/property/{}".format(settings.RETROFIT_MAP_URL, parcel.parcel_id)


def email_parcel_subscribe_to_single_developer(parcel, developer_id):
    subj_template = get_template('mail/notify_selected_developer_subject.txt')
    text_template = get_template('mail/notify_selected_developer_body.txt')
    html_template = get_template('mail/notify_selected_developer_body.html')

    developer = User.objects.get(id=developer_id)

    body_dict = {
        'name': developer.name,
        'parcel_url': create_property_url(parcel),
        'retrofits': format_selected_retrofits(parcel),
        'note': parcel.note,
    }

    subj_text = subj_template.render().rstrip()
    body_text = text_template.render(body_dict)
    body_html = html_template.render(body_dict)

    send_mail(
        subj_text,
        body_text,
        settings.DEFAULT_FROM_EMAIL,
        [developer.email],
        html_message=body_html,
    )


def email_selected_developers(property_manager, note, parcel_ids):
    subj_template = get_template('mail/notify_selected_developer_subject.txt')
    text_template = get_template('mail/notify_selected_developer_body.txt')
    html_template = get_template('mail/notify_selected_developer_body.html')

    developers_and_parcels = [
        (developer_id, parcel)
        for parcel in Parcel.objects
                            .filter(property_manager=property_manager)
                            .filter(parcel_id__in=parcel_ids)
        for developer_id in parcel.selected_developers
    ]

    for (developer_id, parcel) in developers_and_parcels:
        developer = User.objects.get(id=developer_id)

        body_dict = {
            'name': developer.name,
            'parcel_url': create_property_url(parcel),
            'retrofits': format_selected_retrofits(parcel),
            'note': note,
        }

        subj_text = subj_template.render().rstrip()
        body_text = text_template.render(body_dict)
        body_html = html_template.render(body_dict)

        send_mail(
            subj_text,
            body_text,
            settings.DEFAULT_FROM_EMAIL,
            [developer.email],
            html_message=body_html,
        )


def email_parcel_unsubscribe_to_single_developer(parcel, developer_id):
    subj_template = get_template('mail/notify_parcel_unsubscribe_subject.txt')
    text_template = get_template('mail/notify_parcel_unsubscribe_body.txt')
    html_template = get_template('mail/notify_parcel_unsubscribe_body.html')

    developer = User.objects.get(id=developer_id)

    email_dict = {
        'address': parcel.address,
        'name': developer.name,
        'property_manager': parcel.property_manager.name,
        'retrofit_map_url': settings.RETROFIT_MAP_URL,
    }

    send_mail(
        subj_template.render(email_dict).rstrip(),
        text_template.render(email_dict),
        settings.DEFAULT_FROM_EMAIL,
        [developer.email],
        html_message=html_template.render(email_dict),
    )


def email_parcel_unsubscribe_to_developers(parcels_qs):
    subj_template = get_template('mail/notify_parcel_unsubscribe_subject.txt')
    text_template = get_template('mail/notify_parcel_unsubscribe_body.txt')
    html_template = get_template('mail/notify_parcel_unsubscribe_body.html')

    developers_and_parcels = [
        (developer_id, parcel)
        for parcel in parcels_qs
        for developer_id in parcel.selected_developers
    ]

    for (developer_id, parcel) in developers_and_parcels:
        developer = User.objects.get(id=developer_id)

        email_dict = {
            'address': parcel.address,
            'name': developer.name,
            'property_manager': parcel.property_manager.name,
            'retrofit_map_url': settings.RETROFIT_MAP_URL,
        }

        subj_text = subj_template.render(email_dict).rstrip()
        body_text = text_template.render(email_dict)
        body_html = html_template.render(email_dict)

        send_mail(
            subj_text,
            body_text,
            settings.DEFAULT_FROM_EMAIL,
            [developer.email],
            html_message=body_html,
        )
