#!/usr/bin/env python
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

if __name__ == '__main__':
    import r1soft

    parser = r1soft.util.build_option_parser()
    parser.remove_option('--r1soft-host')
    parser.add_option('-d', '--decoration',
        help='Add decoration to the CDP hostname when printing the agents for ' \
            'multiple servers. Leave blank (default) to supress printing the CDP hostname')
    opts, args = parser.parse_args()

    for host in args:
        client = r1soft.cdp3.CDP3Client(host, opts.username, opts.password)
        if opts.decoration:
            print opts.decoration + host + opts.decoration[::-1]
        for agent in client.Agent.service.getAgents():
            print agent.hostname
