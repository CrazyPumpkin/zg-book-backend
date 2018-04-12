#!/usr/bin/env bash

docker exec zg-book-django bash -c '
    source zg_book_docker/lvenv/bin/activate &&
    coverage run --source="src" src/manage.py test src/ &&
    coverage html &&
    coverage-badge -o coverage.svg &&
    cairosvg coverage.svg -o coverage.png
    '
