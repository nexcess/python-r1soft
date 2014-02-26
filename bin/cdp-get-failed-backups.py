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
import time
import multiprocessing.pool

import r1soft

logger = logging.getLogger('cdp-get-failed-backups')

DAY_IN_SECONDS      = 60 * 60 * 24
CDP3_STUCK_DELTA    = DAY_IN_SECONDS
CDP5_STUCK_DELTA    = DAY_IN_SECONDS

def _get_server_time(client):
    # we should check with the server to find out what time it thinks it is
    # and use that for correct time deltas but there doesn't seem to be an
    # API method to get it so we'll just fake it with this for now
    return datetime.datetime.now()

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
            if task.taskType == 'DATA_PROTECTION_POLICY' and 'executionTime' in task]
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
            success = [t.executionTime for t in task_list \
                if t.taskState == 'FINISHED'][-1].replace(microsecond=0)
        except IndexError:
            success = None
        host_result = (agent.hostname, success)
        host_results.append(host_result)
    return (last_successful, host_results)

def handle_cdp5_server(server):
    main_client = r1soft.cdp3.CDP3Client(server['hostname'], server['username'],
        server['password'], server['port'], server['ssl'])
    exec_time_key = lambda task: task.executionTime

    def _handle_policy(policy):
        t_client = r1soft.cdp3.CDP3Client(server['hostname'], server['username'],
            server['password'], server['port'], server['ssl'])

        last_successful = None
        result = None
        stuck = False
        disk_safe = t_client.DiskSafe.service.getDiskSafeByID(policy.diskSafeID)
        agent = t_client.Agent.service.getAgentByID(disk_safe.agentID)
        task_list = sorted(
            (task for task in \
                (t_client.TaskHistory.service.getTaskExecutionContextByID(task_id) \
                    for task_id in t_client.TaskHistory.service.getTaskExecutionContextIDsByAgent(disk_safe.agentID)) \
                if task.taskType == 'DATA_PROTECTION_POLICY' and \
                    'executionTime' in task),
            key=exec_time_key)
        if policy.state in ('OK', 'ALERT'):
            # policy's last run was successful (possibly with alerts)
            running_tasks = sorted(filter(lambda task: task.taskState == 'RUNNING', task_list), key=exec_time_key)
            if running_tasks:
                run_time = _get_server_time(t_client) - running_tasks[-1].executionTime.replace(microsecond=0)
                if (abs(run_time.days * DAY_IN_SECONDS) + run_time.seconds) > CDP5_STUCK_DELTA:
                    stuck = True
                    result = (agent.hostname, '**STUCK** since %s' % \
                        running_tasks[-1].executionTime.replace(microsecond=0))
            if not stuck and (last_successful is None or \
                    last_successful < policy.lastReplicationRunTime):
                last_successful = policy.lastReplicationRunTime.replace(microsecond=0)
        elif policy.state == 'ERROR':
            # policy's last run had an error
            finished_tasks = sorted(filter(lambda task: task.taskState == 'FINISHED', task_list), key=exec_time_key)
            if finished_tasks:
                latest_error_time = finished_tasks[-1].executionTime.replace(microsecond=0)
                result = (agent.hostname, latest_error_time)
            else:
                result = (agent.hostname, '> 30 days')
        else: # policy.state == 'UNKNOWN'
            # policy hasn't been run before ever
            pass
        return (last_successful, result)

    pool = multiprocessing.pool.ThreadPool(4)
    results = pool.map(_handle_policy,
        (p for p in main_client.Policy2.service.getPolicies() \
            if p.enabled and 'diskSafeID' in p))
    try:
        last_successful = max(r[0] for r in results if r[0] is not None)
    except ValueError:
        last_successful = None
    host_results = [r[1] for r in results if r[1] is not None]
    return (last_successful, host_results)

def handle_server(server):
    handle_func = {
        2:  handle_cdp2_server,
        3:  handle_cdp3_server,
        4:  handle_cdp3_server,
        5:  handle_cdp5_server,
    }.get(server['version'])
    try:
        results = (server, False, handle_func(server))
    except Exception as err:
        results = (server, True, err)
    return results

if __name__ == '__main__':
    import sys

    try:
        config = read_config(sys.argv[1])
    except IndexError:
        logger.error('Config file must be the first CLI argument')
        sys.exit(1)

    for (server, has_err, result) in r1soft.util.dispatch_handlers_t(config, handle_server, 4):
        if has_err:
            print '^ %s (CDP%d) ^ ERROR! ^' % (server['hostname'], server['version'])
            print '| %s | %s |' % (result.__class__.__name__, result)
        else:
            print '^ %s (CDP%d) ^ %s ^' % (server['hostname'], server['version'], result[0])
            for host in result[1]:
                print '| %s | %s |' % host
