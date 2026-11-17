#!/bin/bash
set -eu
# shellcheck disable=SC1091
. "${CI_PROJECT_DIR}/build.env"

ios="${APP_ROOT}/ios"
workspace=""
for candidate in "${ios}"/*.xcworkspace; do
  if [ -d "${candidate}" ]; then
    workspace="${candidate}"
    break
  fi
done
if [ -z "${workspace}" ]; then
  echo "Nenhum xcworkspace encontrado em ${ios}."
  exit 1
fi

scheme_file=""
for candidate in "${ios}"/*.xcodeproj/xcshareddata/xcschemes/*.xcscheme; do
  if [ -f "${candidate}" ]; then
    scheme_file="${candidate}"
    break
  fi
done
if [ -z "${scheme_file}" ]; then
  echo "Nenhum scheme compartilhado encontrado em ${ios}."
  exit 1
fi
scheme="$(basename "${scheme_file}" .xcscheme)"

project="$(echo "${ios}"/*.xcodeproj | awk '{print $1}')"
bundle_setting="$(grep -m 1 "PRODUCT_BUNDLE_IDENTIFIER = " "${project}/project.pbxproj" | sed 's/.*= //; s/;//')"
product_name="$(grep -m 1 "PRODUCT_NAME = " "${project}/project.pbxproj" | sed 's/.*= //; s/;//')"

{
  printf 'XCODE_WORKSPACE=%q\n' "${workspace}"
  printf 'XCODE_SCHEME=%q\n' "${scheme}"
  printf 'XCODE_BUNDLE_SETTING=%q\n' "${bundle_setting}"
  printf 'XCODE_PRODUCT_NAME=%q\n' "${product_name}"
} > "${CI_PROJECT_DIR}/xcode.env"

echo "WORKSPACE ${workspace}"
echo "SCHEME ${scheme}"
echo "BUNDLE_SETTING ${bundle_setting}"
echo "PRODUCT_NAME ${product_name}"
echo "xcodebuild $(xcodebuild -version | tr '\n' ' ')"
