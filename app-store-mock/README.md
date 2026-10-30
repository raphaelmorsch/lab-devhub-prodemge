# PRODEMGE App Store Mock

Loja mock da PoC: recebe APKs via API multipart e disponibiliza download na UI.

## API

- `GET /healthz`
- `GET /api/apps`
- `GET /api/apps/{appId}/releases`
- `GET /api/apps/{appId}/releases/{releaseId}`
- `GET /api/apps/{appId}/releases/{releaseId}/download`
- `POST /api/apps/{appId}/releases` — `multipart/form-data` com campo `apk` e metadados (`versionName`, `flavor`, `gitCommit`, `pipelineRun`, …)

## Storage

No OpenShift usa ObjectBucketClaim (`openshift-storage.noobaa.io`). Localmente, sem variáveis S3, grava em `.data/`.

## Deploy

```bash
oc apply -f openshift/obc.yaml
oc new-build --name=app-store-mock --binary --strategy=docker -n prodemge || true
oc start-build app-store-mock --from-dir=. --follow -n prodemge
oc apply -f openshift/deployment.yaml
oc get route app-store-mock -n prodemge
```
