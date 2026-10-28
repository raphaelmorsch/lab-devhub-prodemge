# SISP Mobile — exemplo React Native 0.87.1

Aplicação de laboratório, separada do código institucional do SISP. O projeto parte do template oficial do React Native 0.87.1 e segue o contrato de build Android usado na esteira.

O nome no catálogo é `sidsmobile-rn087`, para poder conviver com o exemplo 0.68.7. O `applicationId` base permanece `com.sidsmobile`.

## Tela no Chrome

Esta entrada só mostra a interface. Ela não gera APK.

```sh
nvm use
npm install
npm run web
```

Abra http://127.0.0.1:5173.

## Build de homologação

```sh
npm install
npm run build:android-homologacao
```

O comando equivale a `cd android && ./gradlew assembleHomologacaoRelease`. Os outros flavors são `desenvolvimento`, `treinamento` e `producao`, com os sufixos `.desenvolvimento`, `.homologacao`, `.treinamento` e `.producao`.

## Ferramentas

| Item | Versão |
|---|---|
| React Native | 0.87.1 |
| Node.js | mínimo >= 22.11.0; pin em 24.12.0 (`.nvmrc` e `.node-version`) |
| JDK | 17 |
| Gradle | 9.4.1 |
| Android Gradle Plugin | resolvido pelo React Native Gradle Plugin |
| Kotlin | 2.2.0 |
| compileSdk / targetSdk / minSdk | 37 / 36 / 24 |
| buildTools | 37.0.0 |
| NDK | 27.1.12297006 |
| Hermes | ligado |
| Nova Arquitetura | ligada |

## Assinatura

O APK de release usa `android/app/sisp-mobile.keystore`, uma chave só de demonstração. Alias `sisp-mobile-demo`, senhas `prodemge-demo`, nas propriedades `MYAPP_UPLOAD_*` de `android/gradle.properties`. Não substitui a keystore de produção.
