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

## Deploy (GitOps / Argo CD)

1. Build da imagem no cluster (`BuildConfig` binário em `prodemge`):

```bash
oc new-build --name=app-store-mock --binary --strategy=docker -n prodemge || true
oc start-build app-store-mock --from-dir=. --follow -n prodemge
```

2. Manifests runtime no GitLab `development/app-store-mock-gitops` (`openshift/`).

3. Application no Janus Argo CD:

```bash
oc apply -f openshift/argocd-application.yaml
```

4. Catálogo RHDH: `catalog-info.yaml` com `argocd/app-selector: backstage-name=app-store-mock`.

### Deploy manual (alternativa)

```bash
oc apply -f openshift/obc.yaml
oc apply -f openshift/deployment.yaml
oc get route app-store-mock -n prodemge
```
