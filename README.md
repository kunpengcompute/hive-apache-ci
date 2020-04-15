# ReadMe

This is a simple script to run Hive tests in parallel on two machines,
this is borrowed and modified from Hive's ptest sripts, it is currently
rewrite for running Hive Apache tests on aarch64: https://builds.apache.org/view/H-L/view/Hive/job/Hive-linux-ARM-trunk/

The configuration file for this script is JSON formated, example:

```
{
  "qfile_hosts": [
  ["jenkins@server1", 1]
  ],

  "other_hosts": [
  ["jenkins@server2", 1]
  ],
  "master_base_path": "/home/jenkins/ptest-workdir/hive",
  "host_base_path": "/home/jenkins/ptest-workdir/data/users/hivetests",
  "java_home": "/usr/lib/jvm/java-8-openjdk-arm64",
  "mvn_path": "/home/jenkins/tools/maven/latest3/",
  "mvn_local_repo": "/home/jenkins/ptest-workdir/.m2/hiverepository/"
}
```

- qfile_hosts
List of hosts that should run TestCliDriver test. Currently we support only one
host and one thread on that host.

- other_hosts
List of hosts that should run all other test cases.  Number has the same meaning
as in `qfile_hosts`.

- master_base_path
Path on localhost (master) where this script can build Hive, store reports, etc.
This path should be available from every slave node and should point to the same
data (home on NFS would be a good choice).  If you specify `HIVE_PTEST_SUFFIX`
environmental variable the actual path used will be
`master_base_path-HIVE_PTEST_SUFFIX`.

- host_base_path
Path on slaves where Hive repo will be cloned and tests will be run.
'-your_user_name' will be actually appended to this path to allow parallel runs
by different users.  `HIVE_PTEST_SUFFIX` affects this path the same as it
affects `master_base_path`, and will be appended if needed.

- java_home
Should point to Java environment that should be used.

- About paths
You can use environmental variables with `${{my_env}}`, as home is used in the
example.

You shouldn't point this paths to your work repository or any directory that
stores data you don't want to lose.  This script might wipe everything under
`master_base_path` and `host_base_path` as needed.

- Example paths
Assuming your user name is 'foo' and you are using example config defined above
this will be final paths used by the script.

```
unset HIVE_PTEST_SUFFIX
master_base_path = /home/foo/hivetests
host_base_path = /mnt/drive/hivetests-foo

export HIVE_PTEST_SUFFIX=second_run
master_base_path = /home/foo/hivetests-second_run
host_base_path = /mnt/drive/hivetests-foo-second_run
```
