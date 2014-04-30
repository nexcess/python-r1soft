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

import logging

import r1soft

logger = logging.getLogger('cdp-server-locations')

def handle_cdp2_server(server):
    agent_status = []
    client = r1soft.cdp2.CDP2Client(server['hostname'], server['username'],
        server['password'], server['port'], server['ssl'])

    for host in (client.host.getHostAsMap(host_id) \
            for host_id in client.host.getHostIds()):
        # check if the agent is enabled and if it has any enabled backup tasks
        active = host['enabled'] and any(task['taskType'] == 'Backup' and task['enabled'] \
            for task in (client.backupTask.getScheduledTaskSummary(tid) \
                for tid in client.backupTask.getScheduledTaskIdsByHost(host['hostID'])))
        agent_status.append({
            'hostname': host['hostname'],
            'description': host['description'],
            'type': r1soft.cdp2.HOST_TYPES[host['hostType']].upper(),
            'active': active,
            'cp_module': host['controlPanelModuleEnabled'],
            'mysql_module': host['cdpForMySqlAddonEnabled'],
        })
    return agent_status

def handle_cdp3_server(server):
    agent_status = []
    client = r1soft.cdp3.CDP3Client(server['hostname'], server['username'],
        server['password'], server['port'], server['ssl'])

    pol2agent = lambda policy: client.Agent.service.getAgentByID( \
        client.DiskSafe.service.getDiskSafeByID(policy.diskSafeID).agentID)

    for agent, policy in ((pol2agent(p), p) \
            for p in client.Policy2.service.getPolicies() if hasattr(p, 'diskSafeID')):
        agent_status.append({
            'hostname': agent.hostname,
            'description': agent.description,
            'type': agent.osType.upper(),
            'active' :policy.enabled,
            'cp_module': False, # we'll just leave this out for now
            'mysql_module': bool(agent.databaseAddOnEnabled and \
                (hasattr(policy, 'databaseInstanceList') and policy.databaseInstanceList)),
        })
    return agent_status

handler_map = {
    2: handle_cdp2_server,
    3: handle_cdp3_server,
    5: handle_cdp3_server,
}


if __name__ == '__main__':
    import sys

    HOST_LIST_HEADER = '^ Hostname ^ Description ^ Backup Server ^ Host Type ^ Enabled ^ MySQL Module ^'
    HOST_LIST_LINE = '| {hostname} | {description} | [[{server_link}|{server_hostname}]] | {type} | {active} | {mysql_module} |'

    SERVER_LIST_HEADER = '^ Backup Server ^ Polling Status ^'
    SERVER_LIST_LINE = '| {server_hostname} | {status} |'

    try:
        config = r1soft.util.read_config(sys.argv[1])
    except IndexError:
        logger.error('Config file must be the first CLI argument')
        sys.exit(1)

    server_results = {}
    agent_lines = []

    def handle_server(server):
        handle_func = handler_map.get(server['version'])
        try:
            results = handle_func(server)
        except Exception as err:
            results = False
        return (server, results)

    print HOST_LIST_HEADER
    for server, results in r1soft.util.dispatch_handlers_t(config, handle_server):
        if results is False:
            server_results[server['hostname']] = False
            continue
        server_results[server['hostname']] = True
        for agent in results:
            agent_lines.append(HOST_LIST_LINE.format(
                server_hostname=server['hostname'],
                server_link=r1soft.util.build_link(server),
                **agent
            ))
    print '\n'.join(sorted(agent_lines))
    print ''
    print SERVER_LIST_HEADER
    for server in server_results:
        print SERVER_LIST_LINE.format(
            server_hostname=server,
            status=server_results[server])
    print ''
