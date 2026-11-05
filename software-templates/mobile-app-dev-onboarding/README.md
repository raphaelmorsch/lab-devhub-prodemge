# Onboarding mobile de Desenvolvimento

Software Template do laboratório. Ele não cria o código da aplicação. A partir de um repositório Git já existente, o template:

- cria o projeto no SonarQube com a action `sonarqube:create-project`
- publica uma entidade no Software Catalog, com a anotação `sonarqube.org/project-key`
- gera o pipeline Tekton `${component_id}-android` no namespace `prodemge`
- grava a configuração do build e a URL da App Store Mock

O flavor é sempre `desenvolvimento`. O pipeline executa Clone, Dependencies, Static Analysis, Build e Publish. Não há task de assinatura da APK: o `assembleDesenvolvimentoRelease` usa a keystore já declarada no Gradle da aplicação. A análise estática roda o SonarScanner e publica o resultado no projeto criado pelo template. O quality gate não interrompe a esteira. O Publish envia o APK para `http://app-store-mock.prodemge.svc:8080` (`enable-publish=true` por padrão). A UI pública fica na Route `app-store-mock` do namespace `prodemge`.

O Scanner usa o token da chave `token` do Secret `sonarqube-credentials`, no namespace `prodemge`. O formulário pede o mesmo token para a action de criação do projeto. A URL interna padrão é `http://sonarqube.sonarqube.svc.cluster.local:9000`. O painel fica em `https://sonarqube-sonarqube.apps.ocp.bct9l.sandbox1479.opentlc.com`.

Um push na branch configurada dispara essa esteira. O EventListener `${component_id}-push` confere o repositório e a branch do webhook. Se a pasta da versão foi informada, o push também precisa alterar arquivos dessa pasta: no monorepositório do laboratório, `sidsmobile-rn-0.87.1` dispara a pilha 0.87.1 e `sidsmobile-rn-0.68.7` dispara a pilha 0.68.7. A revisão do PipelineRun é o commit do push. O segredo do webhook fica no Secret `${component_id}-webhook`.

Na topologia do componente, o ícone de editar código abre o OpenShift Dev Spaces na pasta da versão. O Deployment `${component_id}-code` carrega esse link. O catálogo não fixa `backstage.io/kubernetes-namespace`, para o Developer Hub conseguir ler o CheCluster em `openshift-devspaces`.

As pilhas são React Native 0.68.7 (Node 16.20.2, JDK 11, SDK 33) e 0.87.1 (Node 24.12.0, JDK 17, SDK 37). A task de build é `assembleDesenvolvimentoRelease`.
