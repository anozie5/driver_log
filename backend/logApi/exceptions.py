from rest_framework.exceptions import APIException
from rest_framework import status


class TimeRangeOverlapError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'This time range overlaps with an existing activity log.'
    default_code = 'time_range_overlap'


class InvalidTimeRangeError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid time range.'
    default_code = 'invalid_time_range'


class PermissionDeniedError(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'You do not have permission to perform this action.'
    default_code = 'permission_denied'