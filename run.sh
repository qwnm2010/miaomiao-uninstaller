#!/bin/sh
cd "$(dirname "$0")"
if [ ! -f libmiaomiao.so ] && command -v cc >/dev/null 2>&1; then
  cc -O3 -std=c11 -fPIC -fvisibility=hidden -shared -o libmiaomiao.so native/core.c || true
fi
exec /usr/bin/python3 -B app.py "$@"
