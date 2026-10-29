# ${{ values.component_id }}

Manifestos de onboarding gerados pelo Software Template. O código da aplicação continua em `${{ values.source_url }}`, na revisão `${{ values.source_revision }}`.

O pipeline `${{ values.component_id }}-android`, no namespace `prodemge`, executa:

1. Clone
2. Dependencies
3. Build (`${{ values.flavor }}`)
4. Sign
5. Publish, reservado. O passo existe no pipeline e fica desligado enquanto a loja mock não existir.

Para disparar uma execução, abra o pipeline no console do OpenShift e use o PVC `${{ values.component_id }}-source` como workspace `source`.
