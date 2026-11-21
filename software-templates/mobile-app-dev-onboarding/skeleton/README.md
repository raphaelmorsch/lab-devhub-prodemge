# ${{ values.component_id }}

Manifestos de onboarding gerados pelo Software Template de Desenvolvimento. O código da aplicação continua em `${{ values.source_url }}`, na revisão `${{ values.source_revision }}`.

{%- set platform = values.platform | default('android') -%}
{% if platform != 'ios' %}
O pipeline `${{ values.component_id }}-android`, no namespace `prodemge`, executa clone, dependências, análise estática no SonarQube, build Android e publicação do APK. Não há task de assinatura da APK.
{% endif %}
{% if platform != 'android' %}
O pipeline `${{ values.component_id }}-ios` executa clone, análise estática, pedido de build ao Mac e download do IPA. A publicação do IPA permanece desligada até a App Store Mock aceitar esse pacote. O volume desse pipeline é `${{ values.component_id }}-ios-source`.
{% endif %}

O painel do projeto fica em `${{ values.sonarqube_url }}/dashboard?id=${{ values.component_id }}`.

Um push na branch `${{ values.source_revision }}` de `${{ values.source_url }}` dispara o pipeline desta plataforma.
{%- if values.source_subdirectory %}
Somente alterações em `${{ values.source_subdirectory }}` disparam esta versão. Outra versão no mesmo repositório não inicia esta esteira.
{%- endif %}
A Route do webhook é `${{ values.component_id }}-push`, no namespace `prodemge`. O segredo compartilhado com o Git fica no Secret `${{ values.component_id }}-webhook`. O workspace Android, quando existe, é o PVC `${{ values.component_id }}-source`.

Na topologia do componente, o Deployment `${{ values.component_id }}-code` tem o ícone de editar código. Ele abre o OpenShift Dev Spaces na revisão `${{ values.source_revision }}`{%- if values.source_subdirectory %} da pasta `${{ values.source_subdirectory }}`{%- endif %}.
