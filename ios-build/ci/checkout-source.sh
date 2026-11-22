#!/bin/bash
# Obtém a revisão exata da aplicação. O pipeline de CI e o código compilado são repositórios diferentes.
set -eu

if [ -z "${SOURCE_URL:-}" ] || [ -z "${SOURCE_SHA:-}" ]; then
  echo "SOURCE_URL e SOURCE_SHA são obrigatórios."
  exit 1
fi

dest="${CI_PROJECT_DIR}/source"
rm -rf "${dest}"
git clone "${SOURCE_URL}" "${dest}"
if ! git -C "${dest}" checkout --detach "${SOURCE_SHA}"; then
  echo "Não foi possível obter a revisão ${SOURCE_SHA}."
  exit 1
fi
actual="$(git -C "${dest}" rev-parse HEAD)"
case "${SOURCE_SHA}" in
  *[!0-9a-fA-F]*)
    echo "Revisão ${SOURCE_SHA} resolvida para ${actual}."
    ;;
  *)
    case "${actual}" in
      "${SOURCE_SHA}"*) ;;
      *)
        echo "Revisão obtida ${actual} não corresponde a ${SOURCE_SHA}."
        exit 1
        ;;
    esac
    ;;
esac

app_root="${dest}"
if [ -n "${SOURCE_SUBDIRECTORY:-}" ]; then
  app_root="${dest}/${SOURCE_SUBDIRECTORY}"
fi
if [ ! -f "${app_root}/package.json" ]; then
  echo "package.json não encontrado em ${app_root}."
  exit 1
fi

{
  printf 'APP_ROOT=%q\n' "${app_root}"
  printf 'SOURCE_SHA=%q\n' "${actual}"
} > "${CI_PROJECT_DIR}/build.env"
echo "Aplicação em ${app_root}"
echo "COMMIT ${actual}"
