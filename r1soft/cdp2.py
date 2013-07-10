# -*- coding: utf-8 -*-

# Nexcess.net python-r1soft
# Copyright (C) 2013  Nexcess.net L.L.C.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import logging
import xmlrpclib

logger = logging.getLogger('r1soft.cdp2')

# example: Thu Jun 27 2013 02:03:33 EDT
TIMESTAMP_FMT = '%a %b %d %Y %H:%M:%S %Z'

def build_xmlrpc_url(host, username, password, port=None, ssl=True):
    """
    """

    proto = 'https' if ssl else 'http'
    if port is None:
        port = CDP2Client.PORT_HTTPS if ssl else CDP2Client.PORT_HTTP

    url = '{proto}://{username}:{password}@{host}:{port}/xmlrpc'.format(
        proto=proto,
        username=username,
        password=password,
        host=host,
        port=port
    )
    logger.debug('Built XMLRPC URL: %s', url)
    return url

class CDP2Client(xmlrpclib.ServerProxy):
    """
    """

    PORT_HTTP   = 8084
    PORT_HTTPS  = 8085

    def __init__(self, host, username, password, port=None, ssl=True):
        # looks like ServerProxy is an oldstyle class, can't use super()
        xmlrpclib.ServerProxy.__init__(self, build_xmlrpc_url(
            host, username, password, port, ssl))
