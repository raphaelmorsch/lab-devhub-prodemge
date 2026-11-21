#!/bin/bash
# Gera o archive de device e exporta o IPA de desenvolvimento quando o Mac tem certificado e profile.
set -eu
# shellcheck disable=SC1091
. "${CI_PROJECT_DIR}/build.env"
# shellcheck disable=SC1091
. "${CI_PROJECT_DIR}/xcode.env"

archive="${APP_ROOT}/ios/build/${XCODE_SCHEME}.xcarchive"
export_dir="${CI_PROJECT_DIR}/exported"
log="${CI_PROJECT_DIR}/archive.log"
export_log="${CI_PROJECT_DIR}/export.log"
rm -rf "${archive}" "${export_dir}"
mkdir -p "${export_dir}"

product="${XCODE_PRODUCT_NAME%\"}"
product="${product#\"}"
bundle="${XCODE_BUNDLE_SETTING%\"}"
bundle="${bundle#\"}"
bundle="${bundle//\$(PRODUCT_NAME:rfc1034identifier)/${product}}"

team="$(BUNDLE_ID="${bundle}" python3 - <<'PY'
import glob
import os
import plistlib
import subprocess

bundle = os.environ["BUNDLE_ID"]
homes = [
    os.path.expanduser("~/Library/Developer/Xcode/UserData/Provisioning Profiles"),
    os.path.expanduser("~/Library/MobileDevice/Provisioning Profiles"),
]
for folder in homes:
    for path in glob.glob(os.path.join(folder, "*.mobileprovision")):
        try:
            raw = subprocess.check_output(["security", "cms", "-D", "-i", path], stderr=subprocess.DEVNULL)
            data = plistlib.loads(raw)
        except (subprocess.CalledProcessError, plistlib.InvalidFileException):
            continue
        app_id = data.get("Entitlements", {}).get("application-identifier", "")
        if app_id == bundle or app_id.endswith("." + bundle):
            teams = data.get("TeamIdentifier") or []
            if teams:
                print(teams[0])
                raise SystemExit(0)
raise SystemExit(0)
PY
)"

if [ -z "${team}" ]; then
  {
    echo "IPA_STATUS=blocked-signing"
    echo "MOTIVO=Nenhum provisioning profile deste Mac cobre ${bundle}."
  } > "${CI_PROJECT_DIR}/signing-status.txt"
  echo "IPA_STATUS=blocked-signing"
  exit 0
fi
echo "TEAM ${team}"
echo "BUNDLE ${bundle}"

set +e
xcodebuild \
  -workspace "${XCODE_WORKSPACE}" \
  -scheme "${XCODE_SCHEME}" \
  -configuration Release \
  -destination "generic/platform=iOS" \
  -archivePath "${archive}" \
  -allowProvisioningUpdates \
  DEVELOPMENT_TEAM="${team}" \
  CODE_SIGN_STYLE=Automatic \
  ENABLE_USER_SCRIPT_SANDBOXING=NO \
  archive > "${log}" 2>&1
status=$?
set -e

tail -n 40 "${log}"

if [ "${status}" -ne 0 ] || [ ! -d "${archive}" ]; then
  if grep -E -q "requires a development team|No profiles for|Code Sign error|Provisioning profile|Signing certificate" "${log}"; then
    {
      echo "IPA_STATUS=blocked-signing"
      echo "XCODEBUILD_EXIT=${status}"
      echo "MOTIVO=O archive não assinou ${bundle}."
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
fi

plist="${CI_PROJECT_DIR}/exportOptions.plist"
cat > "${plist}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>method</key>
  <string>debugging</string>
  <key>signingStyle</key>
  <string>automatic</string>
  <key>teamID</key>
  <string>${team}</string>
</dict>
</plist>
EOF

set +e
xcodebuild \
  -exportArchive \
  -archivePath "${archive}" \
  -exportPath "${export_dir}" \
  -exportOptionsPlist "${plist}" \
  -allowProvisioningUpdates > "${export_log}" 2>&1
export_status=$?
set -e

tail -n 40 "${export_log}"

ipa="$(find "${export_dir}" -type f -name '*.ipa' -print | head -n 1)"
if [ "${export_status}" -ne 0 ] || [ -z "${ipa}" ]; then
  {
    echo "IPA_STATUS=export-failed"
    echo "XCODEBUILD_EXIT=${export_status}"
    echo "MOTIVO=O archive existe, mas o export não gerou um IPA."
  } > "${CI_PROJECT_DIR}/signing-status.txt"
  echo "IPA_STATUS=export-failed"
  exit "${export_status}"
fi

{
  echo "IPA_STATUS=exported"
  echo "IPA=${ipa}"
  echo "TEAM=${team}"
  echo "BUNDLE=${bundle}"
} > "${CI_PROJECT_DIR}/signing-status.txt"
echo "IPA_STATUS=exported"
echo "IPA ${ipa}"
