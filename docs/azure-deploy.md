# Azure deployment plan — not deployed

This SEED deliverable is a written alternative. The currently prepared Compose
configuration targets AWS; no Azure resources have been provisioned or tested.

Use Azure Container Apps for the built web/API images, Azure Database for
PostgreSQL Flexible Server with the `vector` extension enabled, a private Qdrant
service with persistent storage, and Azure OpenAI for generation. Confirm the
managed pgvector version supports the application's iterative scans (0.8+) before
choosing it; do not substitute a different store contract silently. See
[Azure pgvector guidance](https://learn.microsoft.com/en-us/azure/postgresql/extensions/how-to-use-pgvector).

Keep one API replica and one Uvicorn worker until distributed rate limiting and
durable jobs exist. Give the API a startup probe that allows model download and
warmup, a readiness probe on `/readyz` and liveness on `/healthz`. Use the
[Container Apps probe reference](https://learn.microsoft.com/en-us/azure/container-apps/health-probes)
when configuring startup/readiness behavior. Run Alembic migrations as an explicit
release job before starting the API revision; do not race migrations across
replicas.

Configure `LABDOCS_LLM_PROVIDER=azure_openai`, the Azure endpoint, deployment,
API version and key through private secrets. The existing provider adapter is
covered by mocked HTTP tests; live deployment access, model behavior and quotas
remain unverified. Store secrets in Key Vault/Container Apps secrets, restrict
network access to Postgres/Qdrant/metrics, terminate TLS at managed ingress and
replace the demo key-entry flow for shared public use.

Persist uploads and the embedding cache, and test coordinated backup/restore of
Postgres, Qdrant and source files. Evaluate cold starts, CPU embedding memory and
provider latency on representative workloads before sizing or setting scaling
policies. No cost or capacity estimate is claimed. The same human-reviewed
quality evaluation and interrupted-job limitations described in
[the AWS plan](aws-deploy.md) apply.
