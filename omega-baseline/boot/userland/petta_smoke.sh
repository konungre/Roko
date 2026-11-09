#!/bin/sh
export SWI_HOME_DIR=/opt/roko/swipl
export PETTA_PATH=/opt/roko/petta
export PYTHONHOME=/opt/roko/python
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
export LD_LIBRARY_PATH=/opt/roko/python/lib:/opt/roko/swipl/lib/x86_64-linux
export HOME=/tmp
export TMPDIR=/tmp
# BusyBox supplies timeout explicitly; no applet symlinks are assumed.
exec /bin/busybox timeout 30 /opt/roko/swipl/bin/x86_64-linux/swipl --stack-limit=64m -q -f none -s /opt/roko/petta-smoke.pl
