#!/bin/bash
set -eu
# shellcheck disable=SC1091
. "${CI_PROJECT_DIR}/build.env"
cd "${APP_ROOT}/ios"

echo "ruby $(ruby -v)"
echo "pod $(pod --version)"
if [ ! -f Podfile ]; then
  echo "Podfile não encontrado em ${APP_ROOT}/ios."
  exit 1
fi
pod install
