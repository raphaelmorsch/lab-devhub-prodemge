# App Store Mock — GitOps

Fonte de verdade: GitLab `development/app-store-mock-gitops`  
Application Argo CD (Janus): `janus-argocd/app-store-mock` → namespace `prodemge`

Sincroniza OBC (NooBaa), Deployment, Service e Route.

A imagem `prodemge/app-store-mock:latest` continua sendo produzida pelo BuildConfig binário no cluster; este repositório controla o runtime.

Catálogo RHDH: componente `app-store-mock` com `argocd/app-selector: backstage-name=app-store-mock`.
