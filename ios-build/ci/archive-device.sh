#!/bin/bash
# Tenta o archive de device. Sem certificado e perfil, registra o bloqueio e não finge que houve IPA.
set -eu
# shellcheck disable=SC1091
. "${CI_PROJECT_DIR}/build.env"
# shellcheck disable=SC1091
. "${CI_PROJECT_DIR}/xcode.env"

archive="${APP_ROOT}/ios/build/${XCODE_SCHEME}.xcarchive"
log="${CI_PROJECT_DIR}/archive.log"
rm -rf "${archive}"

set +e
xcodebuild \
  -workspace "${XCODE_WORKSPACE}" \
  -scheme "${XCODE_SCHEME}" \
  -configuration Release \
  -destination "generic/platform=iOS" \
  -archivePath "${archive}" \
  archive > "${log}" 2>&1
status=$?
set -e

tail -n 60 "${log}"

if [ "${status}" -eq 0 ] && [ -d "${archive}" ]; then
  if [ ! -f "${APP_ROOT}/ios/exportOptions.plist" ]; then
    {
      echo "IPA_STATUS=archive-without-export"
      echo "ARCHIVE=${archive}"
      echo "MOTIVO=Não há exportOptions.plist, certificado ou provisioning profile para exportar um IPA."
    } > "${CI_PROJECT_DIR}/signing-status.txt"
    echo "IPA_STATUS=archive-without-export"
    exit 0
  fi
  echo "IPA_STATUS=export-not-run" > "${CI_PROJECT_DIR}/signing-status.txt"
  exit 0
fi

if grep -E -q "requires a development team|No profiles for|Code Sign error|Provisioning profile|Signing certificate" "${log}"; then
  {
    echo "IPA_STATUS=blocked-signing"
    echo "XCODEBUILD_EXIT=${status}"
    echo "MOTIVO=O Mac não tem certificado Apple nem provisioning profile para este bundle."
  } > "${CI_PROJECT_DIR}/signing-status.txt"
  echo "IPA_STATUS=blocked-signing"
  exit 0
fi

{
  echo "IPA_STATUS=archive-failed"
  echo "XCODEBUILD_EXIT=${status}"
} > "${CI_PROJECT_DIR}/signing-status.txt"
echo "IPA_STATUS=archive-failed"
exit "${status}"
