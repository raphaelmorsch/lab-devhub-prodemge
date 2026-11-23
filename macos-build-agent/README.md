# macOS Build Agent

Processo local do usuário, no mesmo modelo do GitLab Runner: um LaunchAgent, sem porta aberta. A cada 15 segundos ele consulta o Build Coordinator por HTTPS. Quando reserva um job, cria um workspace só daquele build e executa, nesta ordem:

1. `checkout-source.sh`
2. `prepare-node.sh`
3. `prepare-pods.sh`
4. `discover-xcode.sh`
5. `build-simulator.sh`
6. `archive-device.sh`
7. `collect-ipa.sh`

Os scripts são os arquivos versionados em `ios-build/ci`. O job só informa repositório, revisão, pasta, pilha e o conjunto `ios-build-v1`. Qualquer outro conjunto, a pilha 0.68.7 ou uma revisão que pareça opção de comando é recusada antes do shell.

Durante o build o agente renova o lease e envia o `build.log` ao coordenador. No fim envia `output/app.ipa` e remove o código clonado. Sem IPA, registra a falha com o `IPA_STATUS` gravado pelos scripts. O log enviado permanece no coordenador.

A configuração fica em `~/.macos-build-agent/config.json` e o token em `~/.macos-build-agent/token`, ambos fora do Git. O arquivo `route-ca.pem` prende a cadeia da Route. O Python deste Mac não traz essa cadeia da ZeroSSL, e a verificação TLS continua ligada. Os logs ficam em `~/.macos-build-agent/logs/`. O serviço é `com.prodemge.macos-build-agent`.
