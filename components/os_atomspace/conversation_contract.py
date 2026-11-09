"""Closed read-only request for the profile-qualified imported OS observation."""


def validate(request):
    if (type(request) is not dict or set(request)!={'version','operation'}
            or type(request['version']) is not int or request['version']!=1
            or request['operation']!='query_imported_profile'):
        raise ValueError('Require query_imported_profile v1; no paths or mutations accepted')
    return dict(request)
