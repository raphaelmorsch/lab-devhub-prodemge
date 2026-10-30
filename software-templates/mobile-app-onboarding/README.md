# Onboarding de aplicação mobile

Software Template do laboratório. Ele não cria o código da aplicação. A partir de um repositório Git já existente, o template:

- publica uma entidade no Software Catalog
- gera o pipeline Tekton `${component_id}-android` no namespace `prodemge`
- grava a configuração do build e a URL da App Store Mock

O pipeline executa Clone, Dependencies, Build, Sign e Publish. O Publish envia o APK para `http://app-store-mock.prodemge.svc:8080` (`enable-publish=true` por padrão). A UI pública fica na Route `app-store-mock` do namespace `prodemge`.

As pilhas são React Native 0.68.7 (Node 16.20.2, JDK 11, SDK 33) e 0.87.1 (Node 24.12.0, JDK 17, SDK 37). O flavor padrão é `homologacao`, com a task `assembleHomologacaoRelease`.
