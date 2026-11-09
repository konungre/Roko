#!/bin/sh
exec /usr/bin/python3.13 /usr/share/roko/showcase/companion.py --overlay --controller-python /usr/bin/python3.13 --live-request-cli /opt/roko/desktop/live-request/cli.py "$@"
