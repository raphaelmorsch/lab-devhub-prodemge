#!/bin/bash
set -eu
# shellcheck disable=SC1091
. "${CI_PROJECT_DIR}/build.env"
# shellcheck disable=SC1091
. "${CI_PROJECT_DIR}/xcode.env"

derived="${APP_ROOT}/ios/build/DerivedData"
rm -rf "${derived}"
xcodebuild \
  -workspace "${XCODE_WORKSPACE}" \
  -scheme "${XCODE_SCHEME}" \
  -configuration Debug \
  -sdk iphonesimulator \
  -destination "generic/platform=iOS Simulator" \
  -derivedDataPath "${derived}" \
  CODE_SIGNING_ALLOWED=NO \
  build

app="$(find "${derived}/Build/Products" -type d -name '*.app' | head -n 1)"
if [ -z "${app}" ]; then
  echo "O build do simulador não gerou um .app."
  exit 1
fi
{
  echo "SIMULATOR_BUILD=success"
  echo "SIMULATOR_APP=${app}"
  echo "SOURCE_SHA=${SOURCE_SHA}"
} > "${CI_PROJECT_DIR}/simulator-status.txt"
echo "SIMULATOR_APP ${app}"
