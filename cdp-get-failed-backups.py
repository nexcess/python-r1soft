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
import datetime

import r1soft

logger = logging.getLogger('cdp-get-failed-backups')

def read_config(config_filename):
    with open(config_filename) as f:
        config_raw = f.read().strip()
    keys = ['version', 'hostname', 'port', 'ssl', 'username', 'password']
    config = [dict(zip(keys, (field.strip() for field in line.strip().split(':')))) \
            for line in config_raw.split('\n') \
        if line.strip() and not line.startswith('#')]
    for key in ['version', 'port', 'ssl']:
        for server in config:
            server[key] = int(server[key])
    return config

def handle_cdp2_server(server):
    last_successful = None
    host_results = []
    client = r1soft.cdp2.CDP2Client(server['hostname'], server['username'],
        server['password'], server['port'], server['ssl'])

    for host_id in client.host.getHostIds():
        tasks = [client.backupTask.getScheduledTaskSummary(tid) \
            for tid in client.backupTask.getScheduledTaskIdsByHost(host_id)]
        if not [t for t in tasks if t['taskType'] == 'Backup' and t['enabled']]:
            # no enabled backup tasks
            continue
        host = client.host.getHostAsMap(host_id)
        last_backup_task = client.host.getLastFinishedBackupTaskInfo(host_id)
        task_timestamp = datetime.datetime.strptime(last_backup_task[1],
            r1soft.cdp2.TIMESTAMP_FMT)
        host_result = (client.host.getHostname(host_id), task_timestamp)
        if last_successful is None:
            last_successful = task_timestamp
        elif last_successful < task_timestamp:
            last_successful = task_timestamp
        if last_backup_task[0] != 'error':
            continue
        host_results.append(host_result)

    return (last_successful, host_results)

def handle_cdp3_server(server):
    last_successful = None
    host_results = []
    client = r1soft.cdp3.CDP3Client(server['hostname'], server['username'],
        server['password'], server['port'], server['ssl'])

    for policy in client.Policy2.service.getPolicies():
        if not policy.enabled:
            continue
        disksafe = client.DiskSafe.service.getDiskSafeByID(policy.diskSafeID)
        agent = client.Agent.service.getAgentByID(disksafe.agentID)
        task_list = [task for task in (client.TaskHistory.service.getTaskExecutionContextByID(tid) \
                for tid in client.TaskHistory.service.getTaskExecutionContextIDsByAgent(disksafe.agentID)) \
            if task.taskType == 'DATA_PROTECTION_POLICY']
        task_list.sort(key=lambda t: t.executionTime)
        if task_list:
            latest_task = task_list[-1]
            if last_successful is None:
                last_successful = latest_task.executionTime.replace(microsecond=0)
            elif last_successful < latest_task.executionTime:
                last_successful = latest_task.executionTime.replace(microsecond=0)
        if policy.state not in ('ERROR', 'UNKNOWN'):
            continue
        try:
            success = [t.executionTime for t in task_list if t.taskState == 'FINISHED'][-1].replace(microsecond=0)
        except IndexError:
            success = None
        host_result = (agent.hostname, success)
        host_results.append(host_result)
    return (last_successful, host_results)

def handle_cdp5_server(server):
    last_successful = None
    host_results = []
    client = r1soft.cdp3.CDP3Client(server['hostname'], server['username'],
        server['password'], server['port'], server['ssl'])

    for policy in client.Policy2.service.getPolicies():
        if not policy.enabled:
            continue
        try:
            if last_successful is None:
                last_successful = policy.lastReplicationRunTime.replace(microsecond=0)
            elif last_successful < policy.lastReplicationRunTime:
                last_successful = policy.lastReplicationRunTime.replace(microsecond=0)
        except AttributeError:
            continue
        if policy.state not in ('ERROR', 'UNKNOWN'):
            continue
        disksafe = client.DiskSafe.service.getDiskSafeByID(policy.diskSafeID)
        agent = client.Agent.service.getAgentByID(disksafe.agentID)
        task_list = [task for task in (client.TaskHistory.service.getTaskExecutionContextByID(tid) \
                for tid in client.TaskHistory.service.getTaskExecutionContextIDsByAgent(disksafe.agentID)) \
            if task.taskType == 'DATA_PROTECTION_POLICY']
        task_list.sort(key=lambda t: t.executionTime)
        try:
            success = [t.executionTime for t in task_list if t.taskState == 'FINISHED'][-1].replace(microsecond=0)
        except IndexError:
            success = None
        host_result = (agent.hostname, success)
        host_results.append(host_result)
    return (last_successful, host_results)

def handle_server(server):
    handle_func = {
        2:  handle_cdp2_server,
        3:  handle_cdp3_server,
        4:  handle_cdp3_server,
        5:  handle_cdp5_server,
    }.get(server['version'])
    return handle_func(server)

if __name__ == '__main__':
    import sys

    try:
        config = read_config(sys.argv[1])
    except IndexError:
        logger.error('Config file must be the first CLI argument')
        sys.exit(1)

    for server in config:
        try:
            last_successful, results = handle_server(server)
        except Exception as err:
            print '^ %s (CDP%d) ^ ERROR! ^' % (server['hostname'], server['version'])
            print '| %s | %s |' % (err.__class__.__name__, err)
        else:
            print '^ %s (CDP%d) ^ %s ^' % (server['hostname'], server['version'], last_successful)
            for result in results:
                print '| %s | %s |' % result
