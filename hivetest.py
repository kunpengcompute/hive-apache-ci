#!/usr/bin/env python
#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import print_function

import argparse
import time
from threading import Thread
import os.path
import collections
import re
import os

import config

# WARNING
#
# If you are editing this code, please be aware that commands passed to `run`
# should not use single quotes, this will break and end badly as the final
# command looks like `ssh 'host' 'some command - single quote will break it'`.
# Also please be aware that `run` uses `.format` to change `{host}` in commands
# into actual host name it is running on, running `.format` on strings using
# `{host}`, for example including `host_code_path` will not work.
#
# Also this code assumes master_base_path is available to all testing machines
# and is mounted in the same place on all of them.
#
# Getting rid of this restrictions without making the code much more complicated
# is very welcome.

# This is configured in user configuration file.

local = None
qfile_set = None
other_set = None
remote_set = None
all_set = None

master_base_path = None
host_base_path = None
runtest_dir = os.getcwd()

# End of user configurated things.

mvn_path = None
mvn_local_repo = None
code_path = None
host_code_path = None

def read_conf(config_file):
    global local, qfile_set, other_set, remote_set, all_set
    global master_base_path, host_base_path
    global code_path, host_code_path, mvn_path, mvn_local_repo

    if config_file is not None:
        config.load(config_file)
    else:
        config.load()

    local = config.local
    qfile_set = config.qfile_set
    other_set = config.other_set
    remote_set = config.remote_set
    all_set = config.all_set
    mvn_path = config.mvn_path
    mvn_local_repo = config.mvn_local_repo

    master_base_path = config.master_base_path
    host_base_path = config.host_base_path

    if 'HIVE_PTEST_SUFFIX' in os.environ:
        suffix = os.environ['HIVE_PTEST_SUFFIX']
        master_base_path += '-' + suffix
        host_base_path  += '-' + suffix

    code_path = master_base_path + '/hive'
    host_code_path = host_base_path + '/hive-{host}'

    # Setup of needed environmental variables and paths

    # MVN
    all_set.export('MAVEN_HOME', mvn_path)
    all_set.add_path(mvn_path + '/bin')

    # Java
    all_set.export('JAVA_HOME', config.java_home)
    all_set.add_path(config.java_home + '/bin')

    # Hive
    remote_set.export('HIVE_HOME', host_code_path + '/build/dist')
    remote_set.add_path(host_code_path + '/build/dist/bin')

def get_clean_hive():
    # Gets latest Hive from Apache Git repository and cleans the repository
    # (undo of any changes and removal of all generated files).  Also runs
    # `arc-setup` so the repo is ready to be used.
    print('\n-- Updating Hive repo\n')

    local.cd(code_path)
    if local.run('test -d "{0}"'.format(code_path), warn_only = True,
            abandon_output = False) is None:
      local.run('mkdir -p "{0}"'.format(os.path.dirname(code_path)))
      local.run('git clone http://git.apache.org/hive.git "{0}"'.format(code_path))
    else:
      # Clean repo and checkout to t he last revision
      local.run('git reset --hard HEAD')
      local.run('git clean -dffx')
      local.run('git pull')

def copy_local_hive():
    # Copy local repo to the destination path instead of using git clone
    if local.run('test -d "{0}"'.format(code_path), warn_only = True,
            abandon_output = False) is None:
      local.run('mkdir -p "{0}"'.format(os.path.dirname(code_path)))
    local.run('rm -rf "{0}"'.format(code_path), warn_only = True)
    local.run('mkdir -p "{0}"'.format(code_path))
    local.run('echo "{0}"'.format(runtest_dir))
    local.cd(runtest_dir)
    local.run('cp -rf * "{0}"'.format(code_path))
    local.cd(code_path)

def build_hive(remote_build=False):
    if remote_build:
        print('\n-- Building Hive on all machines\n')
        remote_set.cd(host_code_path)
        cmd = 'mvn clean install -e -B -Pdist -Dtar -DskipTests -Dmaven.javadoc.skip -Dmaven.repo.local=' + mvn_local_repo
        remote_set.run(cmd, quiet = True, warn_only = True)
        remote_set.cd(code_path + '/itests')
        remote_set.run(cmd, quiet = True, warn_only = True)
    else:
        print('\n-- Building Hive\n')
        local.cd(code_path)
        cmd = 'mvn clean install -e -B -Pdist -Dtar -DskipTests -Dmaven.javadoc.skip -Dmaven.repo.local=' + mvn_local_repo
        local.run(cmd)
        local.cd(code_path + '/itests')
        local.run(cmd)

def propagate_hive():
    # Expects master_base_path to be available on all test nodes in the same
    # place (for example using NFS).
    print('\n-- Propagating Hive repo to all hosts\n')
    print(host_code_path)
    print(code_path)

    remote_set.run('rm -rf "{0}"'.format(host_code_path))
    remote_set.run('mkdir -p "{0}"'.format(host_code_path))
    remote_set.run('cp -r "{0}/*" "{1}"'.format(
                            code_path, host_code_path))

def run_itests():
    # Runs org.apache.hive:hive-it-qfile testcases.
    print('\n-- Running itests tests on itests hosts\n')

    qfile_set.cd(host_code_path + '/itests')
    cmds = []
    mvn_test = 'mvn test -fn -B -Dmaven.repo.local=' + mvn_local_repo 
    cmds.append(mvn_test + ' -pl '
                '"org.apache.hive:hive-it-qfile" -Dtest=TestEncryptedHDFSCliDriver -Dqfile=encryption_insert_partition_dynamic.q')
    for cmd in cmds:
        qfile_set.run(cmd, quiet = True, warn_only = True)
    collect_reports(qfile_set)

def run_unit_tests():
    # Runs other tests on workers.

    mvn_test = 'mvn test -fn -B -Dmaven.repo.local=' + mvn_local_repo 
    cmds = []
    cmds.append(mvn_test + '-Dtest=TestMetastoreConf')
    other_set.cd(host_code_path)
    # See comment about quiet option in run_tests.
    for cmd in cmds:
        other_set.run(cmd, quiet = True, warn_only = True)
    collect_reports(other_set)

def stop_tests():
    # Brutally stops tests on all hosts, something more subtle would be nice and
    # would allow the same user to run this script multiple times
    # simultaneously.
    print('\n-- Stopping tests on all hosts\n')
    remote_set.run('killall -9 java', warn_only = True)

# -- Tasks that can be called from command line start here.

def cmd_prepare():
    if (args.copylocal):
      copy_local_hive()
    else :
      get_clean_hive()

    collect_reports(local, cleanup=True)
    build_hive()
    propagate_hive()
    build_hive(remote_build=True)

def collect_reports(hosts, local_host=False, cleanup=False):
    if cleanup:
        result_dir = '/home/jenkins/ptest-workdir/data/test_results/'
        hosts.run('rm -rf ' + result_dir + '*')
    elif not local_host:
        result_dir = '/home/jenkins/ptest-workdir/data/test_results/'
        for host in hosts:
            host.cd(host_base_path + '/hive-' + host.hostname)
            host.run('mkdir -p ' + result_dir + host.hostname)
            host.run('find ./  -name "TEST*.xml" -exec cp {} ' + result_dir + host.hostname + ' \;', format_host=False)
    else:
        result_dir = '/home/jenkins/jenkins-slave/workspace/Hive-linux-ARM-trunk/'
        hosts.run('rm -rf ' + result_dir + 'test-results')
        hosts.run('cp -r /home/jenkins/ptest-workdir/data/test_results ' + result_dir)     
        
def cmd_run_tests():

    t = Thread(target = run_unit_tests)
    t.start()
    run_itests()
    t.join()

def cmd_test():
    cmd_prepare()

    local.cd(master_base_path + '/hive')
    local.run('chmod -R 777 *');
    cmd_run_tests()
    
    collect_reports(local, local_host=True)

def cmd_stop():
    stop_tests()

parser = argparse.ArgumentParser(description =
        'Hive test farm controller.')
parser.add_argument('--config', dest = 'config',
        help = 'Path to configuration file')
parser.add_argument('--prepare', action = 'store_true', dest = 'prepare',
        help = 'Builds Hive and propagates it to all test machines')
parser.add_argument('--run-tests', action = 'store_true', dest = 'run_tests',
        help = 'Runs tests on all test machines')
parser.add_argument('--test', action = 'store_true', dest = 'test',
        help = 'Same as running `prepare` and then `run-tests`')
parser.add_argument('--stop', action = 'store_true', dest = 'stop',
        help = 'Kill misbehaving tests on all machines')
parser.add_argument('--copylocal', dest = 'copylocal', action = 'store_true',
        help = 'Copy local repo instead of using git clone and git hub')

args = parser.parse_args()

read_conf(args.config)

if args.prepare:
    cmd_prepare()
elif args.run_tests:
    cmd_run_tests()
elif args.test:
    cmd_test()
elif args.stop:
    cmd_stop()
else:
  parser.print_help()
