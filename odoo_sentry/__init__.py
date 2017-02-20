# -*- coding: utf-8 -*-
# This file is part of Odoo. The COPYRIGHT file at the top level of
# this module contains the full copyright notices and license terms.

import openerp.tools.config as config

from raven import Client, fetch_git_sha
from raven.conf import setup_logging
from raven.exceptions import InvalidGitRepository

from openerp.addons.odoo_sentry.logutils import (
    DEFAULT_LOG_LEVEL,
    LOG_LEVEL_MAP,
    OdooSentryHandler,
    UserErrorFilter,
)


def get_odoo_commit(odoo_dir):
    '''Attempts to get Odoo git commit from :param:`odoo_dir`.'''
    if not odoo_dir:
        return
    try:
        return fetch_git_sha(odoo_dir)
    except InvalidGitRepository:
        pass


def initialize_raven(config):
    client_dsn = config.get('sentry_client_dsn', '').strip()
    enabled = config.get('sentry_enabled', True)
    report_user_errors = config.get('sentry_report_user_errors', False)
    include_extra_context = config.get('sentry_include_context', True)
    level = config.get('sentry_logging_level', DEFAULT_LOG_LEVEL)
    environment = config.get('sentry_environment')
    auto_log_stacks = config.get('sentry_auto_log_stacks', False)
    odoo_dir = config.get('sentry_odoo_dir')

    client = Client(
        client_dsn,
        install_sys_hook=False,
        release=get_odoo_commit(odoo_dir),
        environment=environment,
        auto_log_stacks=auto_log_stacks,
        processors=(
            'openerp.addons.odoo_sentry.logutils.SanitizeOdooCookiesProcessor',
            'raven.processors.SanitizePasswordsProcessor',
        )
    )

    if level not in LOG_LEVEL_MAP:
        level = DEFAULT_LOG_LEVEL

    if enabled:
        handler = OdooSentryHandler(
            include_extra_context,
            client=client,
            level=LOG_LEVEL_MAP[level],
        )
        if not report_user_errors:
            handler.addFilter(UserErrorFilter())
        setup_logging(handler)

    return client


client = initialize_raven(config)
client.captureMessage('Starting Odoo Server')
