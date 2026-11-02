# App Store Mock — GitOps

Fonte de verdade: GitLab `development/app-store-mock-gitops`  
Application Argo CD (Janus): `janus-argocd/app-store-mock` → namespace `prodemge`

Sincroniza OBC (NooBaa), Deployment, Service e Route (`path: openshift`).

A imagem `prodemge/app-store-mock:latest` é produzida pelo BuildConfig binário no cluster; o repositório GitOps controla o runtime.

Catálogo RHDH: componente `app-store-mock` com `argocd/app-selector: backstage-name=app-store-mock`.
