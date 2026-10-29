# Onboarding de aplicação mobile

Software Template do laboratório. Ele não cria o código da aplicação. A partir de um repositório Git já existente, o template:

- publica uma entidade no Software Catalog
- gera o pipeline Tekton `${component_id}-android` no namespace `prodemge`
- grava a configuração do build e o endereço vazio da loja mock

O pipeline executa Clone, Dependencies, Build e Sign. O passo Publish está no desenho e fica desligado (`enable-publish=false`) até a loja mock existir.

As pilhas são React Native 0.68.7 (Node 16.20.2, JDK 11, SDK 33) e 0.87.1 (Node 24.12.0, JDK 17, SDK 37). O flavor padrão é `homologacao`, com a task `assembleHomologacaoRelease`.
