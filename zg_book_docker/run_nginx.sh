#!/usr/bin/env bash

sleep 2
rm /etc/nginx/conf.d/*
cp /opt/zg_app/zg_book_docker/nginx/* /etc/nginx/conf.d/
mkdir -p /etc/nginx/ssl/
cp /opt/zg_app/zg_book_docker/nginx/ssl/* /etc/nginx/ssl/
nginx -g "daemon off;"