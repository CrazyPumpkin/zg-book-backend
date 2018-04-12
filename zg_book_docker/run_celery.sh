#!/usr/bin/env bash

VENV=./zg_book_docker/lvenv

# wait for Broker server to start
sleep 10

lockfile python.lock
rm -f python.lock

source $VENV/bin/activate

cd src
# set -m

if [[ $1 != "beat" ]]; then
    su -m root -c "../$VENV/bin/celery worker -f ../log/celery.log -A zg_book_project.celery -n default@%h -E" # &
else
    rm ../celerybeat.pid
    rm ../celerybeat-schedule
    su -m root -c "../$VENV/bin/celery beat -f ../log/celery.log -A zg_book_project.celery -s ../celerybeat-schedule --pidfile ../celerybeat.pid" # &
fi

# su -m root -c "../$VENV/bin/celery flower -A zg_book_project.celery --basic_auth=admin:qwerty12 > ../log/flower.log 2>&1" &
# fg %1