#!/usr/bin/env sh
set -eu
curl --fail --request POST "http://127.0.0.1:${EXPORTER_PORT:-9101}/scenario/${1:-normal}"
