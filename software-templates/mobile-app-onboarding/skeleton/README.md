# ${{ values.component_id }}

Manifestos de onboarding gerados pelo Software Template. O código da aplicação continua em `${{ values.source_url }}`, na revisão `${{ values.source_revision }}`.

O pipeline `${{ values.component_id }}-android`, no namespace `prodemge`, executa:

1. Clone
2. Dependencies
3. Build (`${{ values.flavor }}`)
4. Sign
5. Publish na App Store Mock

Um push na branch `${{ values.source_revision }}` de `${{ values.source_url }}` dispara o pipeline `${{ values.component_id }}-android`.
{%- if values.source_subdirectory %}
Somente alterações em `${{ values.source_subdirectory }}` disparam esta versão. Outra versão no mesmo repositório não inicia esta esteira.
{%- endif %}
A Route do webhook é `${{ values.component_id }}-push`, no namespace `prodemge`. O segredo compartilhado com o Git fica no Secret `${{ values.component_id }}-webhook`. O workspace continua sendo o PVC `${{ values.component_id }}-source`.

Na topologia do componente, o Deployment `${{ values.component_id }}-code` tem o ícone de editar código. Ele abre o OpenShift Dev Spaces na revisão `${{ values.source_revision }}`{%- if values.source_subdirectory %} da pasta `${{ values.source_subdirectory }}`{%- endif %}.
