#!/bin/bash
set -eu
# shellcheck disable=SC1091
. "${CI_PROJECT_DIR}/build.env"
cd "${APP_ROOT}"

echo "node $(node -v)"
echo "npm $(npm -v)"
if [ "${RN_VERSION:-}" = "rn-0.68.7" ]; then
  echo "React Native 0.68.7 não é compilado com o Xcode instalado neste Mac."
  exit 1
fi

react_native="$(node -p "require('./package.json').dependencies['react-native']")"
echo "REACT_NATIVE=${react_native}"
echo "RN_VERSION_SOLICITADA=${RN_VERSION:-}"

if [ -f package-lock.json ]; then
  npm ci
else
  npm install
fi
