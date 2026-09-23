#!/bin/sh
# Rotate the nginx logs under logs/nginx (policy in logrotate.conf next to this file).
#
# Scheduled in DSM: Control Panel → Task Scheduler → Create → Scheduled Task →
# User-defined script, user `root`, daily. logrotate itself decides when a
# weekly rotation is due, so a daily trigger is fine and self-heals after downtime.
#   sh /volume1/pandya-homelab/deployment/nginx/rotate-logs.sh
# Extra args pass through to logrotate, e.g. a forced verbose run:
#   sudo sh /volume1/pandya-homelab/deployment/nginx/rotate-logs.sh -f -v
#
# Kept in the repo (not /etc/logrotate.d) because DSM upgrades can reset /etc.
# Running as root, logrotate ignores any config not owned by root, and the repo
# copy is owned by avpadmin — so run it from a root-owned temp copy. That trusts
# the repo file exactly as much as this script, which root already runs.
set -eu
if [ "$(id -u)" -ne 0 ]; then
    echo "rotate-logs.sh must run as root (DSM Task Scheduler user 'root', or: sudo sh $0)" >&2
    exit 1
fi
conf=$(mktemp)
trap 'rm -f "$conf"' EXIT
cp /volume1/pandya-homelab/deployment/nginx/logrotate.conf "$conf"
chmod 0644 "$conf"
/bin/logrotate -s /volume1/pandya-homelab/logs/logrotate.state "$@" "$conf"
