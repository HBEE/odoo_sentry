# -*- coding: utf-8 -*-
# This file is part of Odoo. The COPYRIGHT file at the top level of
# this module contains the full copyright notices and license terms.

import logging
import urlparse

import openerp.exceptions
import openerp.http
import openerp.loglevels
import openerp.osv.osv

from raven.handlers.logging import SentryHandler
from raven.utils.wsgi import get_environ, get_headers


# Mapping of Odoo logging level -> Python stdlib logging library log level.
LOG_LEVEL_MAP = dict([
    (getattr(openerp.loglevels, 'LOG_%s' % x), getattr(logging, x))
    for x in ('CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG', 'NOTSET')
])
DEFAULT_LOG_LEVEL = 'warn'


def get_request_info(request):
    '''
    Returns context data extracted from :param:`request`.

    Heavily based on flask integration for Sentry: https://git.io/vP4i9.
    '''
    urlparts = urlparse.urlsplit(request.url)
    return {
        'url': '%s://%s%s' % (urlparts.scheme, urlparts.netloc, urlparts.path),
        'query_string': urlparts.query,
        'method': request.method,
        'headers': dict(get_headers(request.environ)),
        'env': dict(get_environ(request.environ)),
    }


def get_extra_context():
    '''
    Extracts additional context from the current request.
    '''
    request = openerp.http.request
    try:
        session = getattr(request, 'session', {})
    except RuntimeError:
        ctx = {}
    else:
        ctx = {
            'tags': {
                'database': session.get('db', None),
            },
            'user': {
                'login': session.get('login', None),
                'uid': session.get('uid', None),
            },
            'extra': {
                'context': session.get('context', {}),
            },
        }
        if request.httprequest:
            ctx.update({
                'request': get_request_info(request.httprequest),
            })
    return ctx


class UserErrorFilter(logging.Filter):
    '''Logging filter which ignores user errors.'''

    IGNORED_EXCEPTIONS = (
        openerp.exceptions.except_orm,
        openerp.exceptions.AccessDenied,
        openerp.exceptions.Warning,
        openerp.exceptions.RedirectWarning,
        openerp.osv.osv.except_osv,
    )

    def filter(self, record):
        if record.exc_info and all(record.exc_info):
            _, exc_value, _ = record.exc_info

            if isinstance(exc_value, self.IGNORED_EXCEPTIONS):
                return False

        return True


class OdooSentryHandler(SentryHandler):
    '''
    Customized :class:`raven.handlers.logging.SentryHandler`.

    Allows to add additional Odoo and HTTP request data to the message
    which is sent to Sentry.
    '''

    def __init__(self, include_extra_context, *args, **kwargs):
        super(OdooSentryHandler, self).__init__(*args, **kwargs)
        self.include_extra_context = include_extra_context

    def emit(self, record):
        if self.include_extra_context:
            self.client.context.merge(get_extra_context())
        super(OdooSentryHandler, self).emit(record)
