import bisect
import json
from datetime import datetime
from django.core.exceptions import (PermissionDenied,
                                    ValidationError,
                                    ObjectDoesNotExist)
from django.db import transaction
from rest_framework import generics, viewsets, status, views
from rest_framework.exceptions import (ParseError,
                                       NotFound)
from rest_framework.decorators import (api_view, permission_classes,
                                       detail_route, list_route)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
import requests
from rest_auth.views import LoginView, LogoutView
from allauth.account.utils import (complete_signup,
                                   setup_user_email,
                                   send_email_confirmation)
from allauth.account.models import EmailAddress
import rollbar

from api.serializers import (PropertyManagerSerializer, UserSerializer,
                             RetrofitDeveloperInfoSerializer,
                             CreatePropertyManagerSerializer,
                             ParcelSerializer)
from api.models import PropertyManager, User, Parcel
from api.permissions import IsPwdStaff
from api.libs import (email_parcel_unsubscribe_to_developers,
                      email_property_manager, email_selected_developers,
                      email_parcel_unsubscribe_to_single_developer,
                      email_parcel_subscribe_to_single_developer,
                      send_property_manager_preferences_email)
from api.errors import (ParcelsAlreadySubmitted,
                        ServerError,
                        BadRequest,
                        ServiceUnavailable)


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint for CRUD ops on User objects.
    """
    queryset = User.objects.all().order_by('id')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsPwdStaff, ]

    def partial_update(self, request, pk=None):
        status = request.data.get('status', None)
        reason_for_denial = request.data.get('reason_for_denial', '')

        if status:
            timestamp = datetime.now()
            developer = self.queryset.get(id=pk)

            if status == User.STATUS_DENIED:
                developer.status = User.STATUS_DENIED
                developer.denied_at = timestamp
                developer.reason_for_denial = reason_for_denial
                developer.approved_at = None
                developer.deactivated_at = None
            elif status == User.STATUS_ACTIVE:
                developer.status = User.STATUS_ACTIVE
                developer.approved_at = timestamp
                developer.denied_at = None
                developer.deactivated_at = None
                developer.reason_for_denial = ""
            elif status == User.STATUS_DEACTIVATED:
                developer.status = User.STATUS_DEACTIVATED
                developer.deactivated_at = timestamp
                developer.reason_for_denial = ""

            developer.save()
            return Response(UserSerializer(developer).data)

        return super(UserViewSet, self).partial_update(request, pk)

    @transaction.atomic
    @detail_route(methods=['DELETE'],
                  permission_classes=[IsPwdStaff],
                  url_path='customers/(?P<manager_id>[0-9]+)')
    def managers(self, request, pk, manager_id):
        developer = self.get_object()

        parcels = Parcel.objects \
                        .all() \
                        .filter(property_manager_id=int(manager_id)) \
                        .filter(selected_developers__contains=[developer.id])

        for parcel in parcels:
            parcel.selected_developers.remove(developer.id)
            parcel.save()

        return Response(status=status.HTTP_204_NO_CONTENT)


class ParcelViewSet(viewsets.ModelViewSet):
    queryset = Parcel.objects.all().order_by('id')
    serializer_class = ParcelSerializer

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsPwdStaff(), ]
        elif self.action == 'resend_manager_email':
            return [AllowAny(), ]
        else:
            return [IsAuthenticated(), ]

    @transaction.atomic
    def create(self, request):
        parcel = Parcel.objects.create(
            parcel_id=request.data['parcel_id'],
            address=request.data['address'],
            property_manager_id=request.data['property_manager'],
            building_type=request.data['building_type'],
            cistern=request.data['cistern'],
            green_roof=request.data['green_roof'],
            rain_garden=request.data['rain_garden'],
            subsurface_storage=request.data['subsurface_storage'],
            permeable_pavement=request.data['permeable_pavement'],
            selected_developers=request.data['selected_developers'],
            accepts_contacts=request.data['accepts_contacts']
        )

        for dev_id in parcel.selected_developers:
            email_parcel_subscribe_to_single_developer(parcel, dev_id)

        return Response(ParcelSerializer(parcel).data)

    @transaction.atomic
    def destroy(self, request, pk):
        try:
            parcel = self.queryset.get(id=pk)

            email_parcel_unsubscribe_to_developers(self.queryset.filter(id=pk))

            remaining_manager_parcels = (
                self.queryset
                .filter(property_manager=parcel.property_manager)
                .exclude(id=pk)
            )
            remaining_developers = [
                item for sublist
                in [p.selected_developers for p in remaining_manager_parcels]
                for item in sublist
            ]
            unselected_developers = [
                developer for developer
                in parcel.selected_developers
                if developer not in remaining_developers
            ]

            parcel.delete()
            return Response(unselected_developers, status=status.HTTP_200_OK)

        except Parcel.DoesNotExist:
            return Response([], status=status.HTTP_200_OK)

    @list_route(methods=['GET'])
    def saved(self, request):
        return Response(request.user.saved_parcel_ids)

    @list_route(methods=['GET'])
    def interested(self, request):
        return Response(request.user.interested)

    @list_route(methods=['GET'])
    def enrolled(self, request):
        return Response(request.user.enrolled)

    @detail_route(methods=['POST', 'DELETE'])
    @transaction.atomic
    def save(self, request, pk=None):
        try:
            parcel_id = int(pk)
        except TypeError:
            return Response('Parcel ID must be an integer',
                            status=status.HTTP_400_BAD_REQUEST)
        if request.method == 'POST':
            # This is not efficient, but we expect the list of parcels to be
            # less than 100.
            if parcel_id not in request.user.saved_parcel_ids:
                bisect.insort(request.user.saved_parcel_ids, parcel_id)
                request.user.save()
        elif request.method == 'DELETE':
            try:
                request.user.saved_parcel_ids.remove(parcel_id)
            except ValueError:
                # If the requested parcel ID is not in the list it is
                # effectively the same as a successful removal
                pass
            request.user.save()

        return Response(request.user.saved_parcel_ids)

    @detail_route(methods=['POST'],
                  permission_classes=[AllowAny])
    def resend_manager_email(self, request, pk):
        try:
            parcel = Parcel.objects.get(parcel_id=pk)
            send_property_manager_preferences_email(parcel)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Parcel.DoesNotExist:
            raise ValidationError('Invalid request')


@permission_classes((AllowAny,))
class SubmitRetrofitDeveloperForm(generics.CreateAPIView):
    serializer_class = UserSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        setup_user_email(self.request, user, [])

        complete_signup(self.request._request, user,
                        'optional',
                        None)


@permission_classes((IsPwdStaff,))
class DashboardSubmitRetrofitDeveloperForm(generics.CreateAPIView):
    serializer_class = UserSerializer

    def perform_create(self, serializer):
        user = serializer.save()

        # The developer starts off with status approved if
        # the admin is creating the account
        user.approved_at = datetime.now()
        user.has_admin_generated_password = True
        user.save()

        # Because it's an admin action, assume
        # the email is already "verified"
        setup_user_email(self.request, user, [])
        email_address = EmailAddress.objects.get_primary(user.id)
        if email_address:
            email_address.verified = True
            email_address.save()


@permission_classes((IsPwdStaff,))
class ResendRetrofitDeveloperEmailVerifyLink(views.APIView):
    def get(self, request, format=None):
        """
        Resend the email verification link to a user
        """
        try:
            user_id = request.query_params['user_id']
        except KeyError:
            raise ParseError(detail='Missing required url parameter: user_id')

        try:
            user = User.objects \
                       .filter(is_staff=False) \
                       .get(id=user_id)
            send_email_confirmation(self.request._request, user)
            return Response()
        except ObjectDoesNotExist:
            raise NotFound(detail='Could not find requested user')


class PropertyManagerViewSet(viewsets.ModelViewSet):
    """
    API endpoint for CRUD ops on PropertyManager objects.
    """
    queryset = PropertyManager.objects.all().order_by('name')
    serializer_class = PropertyManagerSerializer

    @transaction.atomic
    def destroy(self, request, pk):
        try:
            manager = self.queryset.get(id=pk)

            email_parcel_unsubscribe_to_developers(manager.parcels.all())

            manager.delete()
            return Response([], status=status.HTTP_200_OK)

        except PropertyManager.DoesNotExist:
            return Response([], status=status.HTTP_200_OK)

    @transaction.atomic
    @detail_route(methods=['DELETE'],
                  permission_classes=[IsPwdStaff],
                  url_path='developers/(?P<developer_id>[0-9]+)')
    def developers(self, request, pk, developer_id):
        manager = self.get_object()

        parcels = manager.parcels \
                         .filter(selected_developers__contains=[developer_id])

        for parcel in parcels:
            parcel.selected_developers.remove(int(developer_id))
            parcel.save()
            email_parcel_unsubscribe_to_single_developer(parcel, developer_id)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @list_route(methods=['GET', 'PUT', 'DELETE'],
                permission_classes=[AllowAny])
    def preferences(self, request):
        missing_token_error = ValidationError('Token not provided')
        token = request.GET.get('token')

        if not token:
            raise missing_token_error

        try:
            manager = PropertyManager.objects.get(unsubscribe_token=token)
        except PropertyManager.DoesNotExist:
            raise missing_token_error

        parcel_qs = Parcel.objects.filter(property_manager=manager)

        if request.method == 'GET':
            return Response([ParcelSerializer(p).data for p in parcel_qs])
        elif request.method == 'DELETE':
            parcel_ids = request.data['parcel_ids']
            parcel_qs = Parcel.objects \
                              .filter(property_manager=manager) \
                              .filter(parcel_id__in=parcel_ids)

            email_parcel_unsubscribe_to_developers(parcel_qs)

            parcel_qs.delete()

            return Response(status=status.HTTP_204_NO_CONTENT)
        elif request.method == 'PUT':
            parcel = Parcel.objects \
                           .filter(property_manager=manager) \
                           .get(id=request.data['id'])

            selected_developers = request.data['selected_developers']

            unselected_developers = [
                developer for developer
                in parcel.selected_developers
                if developer not in selected_developers
            ]

            newly_selected_developers = [
                developer for developer
                in selected_developers
                if developer not in parcel.selected_developers
            ]

            parcel.selected_developers = selected_developers
            parcel.cistern = request.data['cistern']
            parcel.rain_garden = request.data['rain_garden']
            parcel.green_roof = request.data['green_roof']
            parcel.permeable_pavement = request.data['permeable_pavement']
            parcel.subsurface_storage = request.data['subsurface_storage']
            parcel.accepts_contacts = request.data['accepts_contacts']
            parcel.save()

            for developer in unselected_developers:
                email_parcel_unsubscribe_to_single_developer(parcel, developer)

            for developer in newly_selected_developers:
                email_parcel_subscribe_to_single_developer(parcel, developer)

            return Response(ParcelSerializer(parcel).data)

    @transaction.atomic
    def perform_update(self, serializer):
        new_note = self.request.data['note']
        manager_id = self.request.data['id']

        Parcel.objects \
              .filter(property_manager=manager_id) \
              .update(note=new_note)

        return super(PropertyManagerViewSet, self).perform_update(serializer)


@permission_classes((AllowAny,))
class SubmitManagerForm(generics.CreateAPIView):
    serializer_class = CreatePropertyManagerSerializer

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        try:
            manager = PropertyManager.objects.get(email=request.data['email'])
            return self.update_manager(manager, request.data)
        except PropertyManager.DoesNotExist:
            return self.create(request, *args, **kwargs)

    def update_manager(self, manager, post_data):
        selected_developers = post_data.get('selected_developers', [])
        rain_garden = post_data.get('rain_garden', False)
        subsurface_storage = post_data.get('subsurface_storage', False)
        green_roof = post_data.get('green_roof', False)
        permeable_pavement = post_data.get('permeable_pavement', False)
        cistern = post_data.get('cistern', False)
        note = post_data.get('note', '')
        parcels = post_data.get('parcels', [])
        accepts_contacts = post_data.get('accepts_contacts', True)

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
                                      note=note,
                                      accepts_contacts=accepts_contacts)

        if (len(existing_parcels)):
            raise ParcelsAlreadySubmitted({
                "parcels":
                    [
                        "Parcel at {} already submitted".format(p["address"])
                        for p in existing_parcels
                    ]
                }, code=400)

        manager.prefer_email = post_data.get('prefer_email',
                                             manager.prefer_email)
        manager.prefer_phone = post_data.get('prefer_phone',
                                             manager.prefer_phone)
        manager.phone = post_data.get('phone', manager.phone)

        manager.save()

        parcel_ids = [parcel['id'] for parcel in parcels]
        email_property_manager(manager, note, selected_developers, parcel_ids)
        email_selected_developers(manager, note, parcel_ids)

        return Response(CreatePropertyManagerSerializer(manager).data)


class RetrofitDeveloperListView(generics.ListAPIView):
    queryset = User.objects \
                   .filter(is_staff=False) \
                   .order_by('-id')


@permission_classes((AllowAny,))
class RetrofitDeveloperMarketingListView(RetrofitDeveloperListView):
    serializer_class = RetrofitDeveloperInfoSerializer

    def get_queryset(self):
        return User.objects \
                   .filter(is_staff=False) \
                   .filter(status=User.STATUS_ACTIVE) \
                   .order_by('-id')


class RetrofitDeveloperAdminListView(RetrofitDeveloperListView):
    serializer_class = UserSerializer


def post_web_api_rollbar_error(request, status_code=None):
    message = "{} error connecting to PWD WebAPI".format(
        status_code if status_code else "ConnectionError")

    rollbar.report_message(message, 'error', request)


@api_view(['GET', 'POST', 'PUT'])
@permission_classes((AllowAny,))
def make_pwd_webapi_request(request, path, api_root):
    webapi_url = '{}/{}?{}'.format(api_root,
                                   path,
                                   request.META['QUERY_STRING'])
    body_json = json.loads(request.body.decode('utf-8')) if request.body \
        else None
    method = requests.post if request.method == 'PUT' else requests.get

    try:
        r = method(webapi_url, json=body_json)
        status_code = r.status_code

        if status_code == 200:
            return Response(r.json(), status=status_code)

        post_web_api_rollbar_error(request, status_code)

        if status_code == 404:
            raise NotFound(detail=r.reason, code=status_code)
        elif status_code == 500:
            raise ServerError(detail=r.reason)
        elif r.status_code == 503:
            raise ServiceUnavailable(detail=r.reason)
        else:
            raise BadRequest(detail=r.reason)
    except requests.ConnectionError:
        post_web_api_rollbar_error(request)
        raise ServiceUnavailable(detail='Could not connect to API')


class LoginToAdminDashboard(LoginView):
    def post(self, request, *args, **kwargs):
        if not IsPwdStaff.has_permission(IsPwdStaff,
                                         request,
                                         self,
                                         request.data.get('email', None)):
            raise PermissionDenied()
        return super(LoginToAdminDashboard, self).post(request,
                                                       *args,
                                                       **kwargs)

    def get(self, request, *args, **kwargs):
        if not (IsPwdStaff.has_permission(IsPwdStaff, request, self)
                and request.user.is_authenticated):
            raise PermissionDenied()
        return Response()


class LogoutOfAdminDashboard(LogoutView):
    pass


class LoginToRetrofitMap(LoginView):
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated():
            raise PermissionDenied()

        return Response({
            'status': request.user.status,
            'isStaff': request.user.is_staff,
        })

    def post(self, request, *args, **kwargs):
        response = super(LoginToRetrofitMap, self) \
                   .post(request, *args, **kwargs)
        response.data['status'] = self.user.status
        response.data['isStaff'] = self.user.is_staff
        return response


class LogoutOfRetrofitMap(LogoutView):
    pass
