#!/bin/bash

VENV=./zg_book_docker/lvenv

# Remove lock if it's active for some reason
rm -f python.lock

# Lock until venv installation and migration are completed
lockfile python.lock

# if directory not exists
if [ ! -d "$VENV" ]; then
    # create venv
    virtualenv $VENV
fi

source $VENV/bin/activate

# Read sha1 sum to variable
sha1old="$(head -n 1 $VENV/sha1.sum)"
sha1req="$(sha1sum requirements.txt)"
sha1old=${sha1old:0:40}
sha1req=${sha1req:0:40}

# if file doesn't exists or sha1 sum is different
if [ ! -f $VENV/sha1.sum ] || [[ $sha1old != $sha1req ]]; then
    pip install -U -r requirements.txt;
    pip install uwsgi;
    echo $sha1req > $VENV/sha1.sum;
fi

python3 src/manage.py migrate
python3 src/manage.py collectstatic --no-input

rm -f python.lock

#python3 src/manage.py runserver 0.0.0.0:8000
uwsgi --yaml ./zg_book_docker/uwsgi.yml