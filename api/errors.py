from rest_framework.exceptions import APIException, ValidationError


class ParcelsAlreadySubmitted(ValidationError):
    pass


class ServerError(APIException):
    status_code = 500
    default_detail = 'Internal server error'
    default_code = 'internal_server_error'


class BadRequest(APIException):
    status_code = 400
    default_detail = 'Bad request'
    default_code = 'bad_request'


class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = 'Service unavailable'
    default_code = 'service_unavailable'
