#!/bin/bash
# Copia o IPA exportado para output/, de onde o Tekton baixa o artefato.
# Sem IPA, preserva o status de assinatura e não inventa um pacote.
set -eu

output="${CI_PROJECT_DIR}/output"
mkdir -p "${output}"

if [ -f "${CI_PROJECT_DIR}/signing-status.txt" ]; then
  cp "${CI_PROJECT_DIR}/signing-status.txt" "${output}/signing-status.txt"
fi

found=""
for folder in "${CI_PROJECT_DIR}/exported" "${CI_PROJECT_DIR}/source"; do
  if [ -d "${folder}" ]; then
    found="$(find "${folder}" -type f -name '*.ipa' -print | head -n 1)"
    if [ -n "${found}" ]; then
      break
    fi
  fi
done
if [ -n "${found}" ]; then
  cp "${found}" "${output}/app.ipa"
  echo "IPA_FILE=${output}/app.ipa"
  exit 0
fi

echo "Nenhum IPA para coletar."
if [ -f "${output}/signing-status.txt" ]; then
  cat "${output}/signing-status.txt"
fi
