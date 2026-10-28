# SISP Mobile — exemplo React Native 0.68.7

Aplicação de laboratório, separada do código institucional do SISP. O projeto parte do template oficial do React Native 0.68.7 e segue o contrato de build Android usado na esteira.

O nome no catálogo é `sidsmobile-rn068`, para poder conviver com o exemplo 0.87.1. O `applicationId` base permanece `com.sidsmobile`.

## Build de homologação

```sh
npm install
npm run build:android-homologacao
```

O comando equivale a `cd android && ./gradlew assembleHomologacaoRelease`. Os outros flavors são `desenvolvimento`, `treinamento` e `producao`, com os sufixos `.desenvolvimento`, `.homologacao`, `.treinamento` e `.producao`.

## Ferramentas

| Item | Versão |
|---|---|
| React Native | 0.68.7 |
| Node.js | >= 14 (`.nvmrc` em 16) |
| JDK | 11 |
| Gradle | 7.3.3 |
| Android Gradle Plugin | 7.0.4 |
| Kotlin | 1.9.22 |
| compileSdk / targetSdk / minSdk | 33 / 33 / 23 |
| buildTools | 30.0.2 |
| NDK | 21.3.6528147 |
| Hermes | desligado (JavaScriptCore) |
| Nova Arquitetura | desligada |

A especificação do SISP cita o Android Gradle Plugin 4.2.2. Esta versão do React Native não compila com esse plugin: o template oficial usa o 7.0.4, e é esse valor que o exemplo mantém.

## Assinatura

O APK de release usa `android/app/sisp-mobile.keystore`, uma chave só de demonstração. Alias `sisp-mobile-demo`, senhas `prodemge-demo`, nas propriedades `MYAPP_UPLOAD_*` de `android/gradle.properties`. Não substitui a keystore de produção.
