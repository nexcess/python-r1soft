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
import suds
import time
import urllib2
import ssl
from .sslcontext import create_ssl_context, HTTPSTransport

logger = logging.getLogger('r1soft.cdp3')

def build_wsdl_url(host, namespace, port=None, ssl=True):
    """Build WSDL URL for CDP3+ API
    """

    proto = 'https' if ssl else 'http'
    if port is None:
        port = CDP3Client.PORT_HTTPS if ssl else CDP3Client.PORT_HTTP

    url = '{proto}://{host}:{port}/{namespace}?wsdl'.format(
        proto=proto,
        host=host,
        port=port,
        namespace=namespace
    )
    logger.debug('Built WSDL url: %s', url)
    return url

class PoodleSSLSocket(ssl.SSLSocket):
    """Use TLSv1 by default for SSL connections thanks to SSLv3 being disabled
    in the R1soft update
    """
    def __init__(self, *pargs, **kwargs):
        kwargs['ssl_version'] = ssl.PROTOCOL_TLSv1
        super(PoodleSSLSocket, self).__init__(*pargs, **kwargs)

ssl.SSLSocket = PoodleSSLSocket

UNSAFE_HttpsNoVerifyTransport = lambda **kwargs: HTTPSTransport(context=create_ssl_context(verify=False), **kwargs)

class SoapClientWrapper(object):
    def __init__(self, real_client, **kwargs):
        self._options = kwargs
        self._real_client = real_client
        self._post_init()

    def __getattr__(self, name):
        return getattr(self._real_client.service, name)

    def __call__(self, *args, **kwargs):
        return self._real_client.factory.create(*args, **kwargs)

    def _post_init(self):
        if self._options.get('backwards_compat', True):
            self.service = self
            self.factory = self
            self.create = self.__call__

class SoapRateLimiter(SoapClientWrapper):
    def _post_init(self):
        super(SoapRateLimiter, self)._post_init()
        rate_limit = self._options.get('rate_limit', None)
        if rate_limit is None:
            self._rl_hz = 0
        else:
            self._rl_hz = 1.0 / (rate_limit * 1.0)
        self._rl_prev = time.time()

    def __getattr__(self, name):
        func = super(SoapRateLimiter, self).__getattr__(name)
        def rate_limit_wrapper(*args, **kwargs):
            now = time.time()
            delta = max(0, now - self._rl_prev)
            if delta < self._rl_hz:
                sleep_time = self._rl_hz - delta
                logger.debug('Sleeping for %0.8d seconds for rate limiting', sleep_time)
                time.sleep(sleep_time)
            self._rl_prev = time.time()
            return func(*args, **kwargs)
        return rate_limit_wrapper

class SoapRetrier(SoapRateLimiter):
    def __getattr__(self, name):
        func = super(SoapRetrier, self).__getattr__(name)
        def retrier_wrapper(*args, **kwargs):
            final_error = None
            for i in xrange(self._options.get('retries', 1)):
                try:
                    result = func(*args, **kwargs)
                except urllib2.URLError as err:
                    logger.warn('Got error response')
                    logger.exception(err)
                    final_error = err
                    continue
                else:
                    return result
            else:
                logger.error('No more retries')
                raise final_error
        return retrier_wrapper

class CDP3Client(object):
    """SOAP client for CDP3+ API
    """

    PORT_HTTP   = 9080
    PORT_HTTPS  = 9443

    def __init__(self, host, username, password, port=None, ssl=True, verify_ssl=False, **kwargs):
        # in a perfect world, verify_ssl would default to True but we'll leave
        # it at False for now to make life easier
        self.__namespaces = {}
        self._host = host
        self._username = username
        self._password = password
        self._port = port
        self._ssl = ssl
        self._verify_ssl = verify_ssl
        self._init_args = kwargs

    def __getattr__(self, name):
        logger.debug('Loading SOAP client for namespace: %s', name)
        ns = self.__namespaces.get(name, None)
        if ns is None:
            logger.debug('Client doesn\'t exist, creating client for ' \
                'namespace: %s', name)
            ns = SoapRetrier(
                suds.client.Client(
                    build_wsdl_url(self._host, name, self._port, self._ssl),
                    username=self._username,
                    password=self._password,
                    transport=UNSAFE_HttpsNoVerifyTransport(
                            username=self._username, password=self._password) \
                        if (self._ssl and not self._verify_ssl) else None,
                    **self._init_args),
                rate_limit=None,
                retries=3,
                backwards_compat=True
                )
            self.__namespaces[name] = ns
        return ns

    def build_object(self, namespace, object_type, attributes):
        object_instance = getattr(self, namespace).factory.create(object_type)

        for key, value in attributes.iteritems():
            if type(value) == tuple:
                attr_type = getattr(self, namespace).factory.create(value[0])
                attr_value = getattr(attr_type, value[1])
                setattr(object_instance, key, attr_value)
            else:
                setattr(object_instance, key, value)

        return object_instance
