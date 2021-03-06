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

import optparse
import os
import time

try:
    import multiprocessing
    import multiprocessing.pool
except ImportError:
    multiprocessing = None

from .cdp2 import CDP2Client
from .cdp3 import CDP3Client

def build_option_parser(parser=None):
    if parser is None:
        parser = optparse.OptionParser()
    parser.add_option('-r', '--r1soft-host',
        help='R1Soft API hostname')
    parser.add_option('-u', '--username',
        help='R1Soft API username',
        default=os.environ.get('R1SOFT_USERNAME', 'admin'))
    parser.add_option('-p', '--password',
        help='R1Soft API password',
        default=os.environ.get('R1SOFT_PASSWORD', ''))
    return parser

def read_config(config_filename):
    with open(config_filename) as f:
        config_raw = f.read().strip()
    keys = ['version', 'hostname', 'port', 'ssl', 'username', 'password']
    config = [dict(zip(keys, (field.strip() for field in line.strip().split(':')))) \
            for line in config_raw.split('\n') \
        if line.strip() and not line.startswith('#')]
    int_keys = ['version', 'port', 'ssl']
    for server in config:
        for key in int_keys:
            server[key] = int(server[key])
    return config

def build_link(server):
    return '{proto}://{hostname}:{port}/'.format(
        hostname=server['hostname'],
        port=8001 if server['ssl'] else 8000,
        proto='https' if server['ssl'] else 'http'
    )

def dispatch_handlers(config, server_handler):
    for server in config:
        yield (server, server_handler(server))

def dispatch_handlers_mp(config, server_handler, workers=None):
    if multiprocessing is None:
        return dispatch_handlers(config, server_handler)
    else:
        pool = multiprocessing.Pool(workers)
        return pool.map(server_handler, config)

def dispatch_handlers_t(config, server_handler, workers=None):
    if multiprocessing is None:
        return dispatch_handlers(config, server_handler)
    else:
        pool = multiprocessing.pool.ThreadPool(workers)
        return pool.map(server_handler, config)

def build_cdp2_client(server):
    return CDP2Client(server['hostname'], server['username'],
        server['password'], server['port'], server['ssl'])

def build_cdp3_client(server):
    return CDP3Client(server['hostname'], server['username'],
        server['password'], server['port'], server['ssl'])

def rate_limit(limit, iterator):
    hz = 1.0 / (limit * 1.0)
    prev = time.time()
    for item in iterator:
        now = time.time()
        delta = max(0, now - prev)
        if delta < hz:
            time.sleep(hz - delta)
        prev = time.time()
        yield item
