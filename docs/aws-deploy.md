# AWS deployment preparation — not deployed

This is an operating plan and Compose configuration, not a deployed service.
No EC2 instance, network, load balancer, DNS record or other AWS resource has been
created. Local container tests and mocked provider tests do not establish cloud
availability, a security certification or live model quality.

## Shape of the deployment

Use one Linux EC2 host running Docker Compose, with persistent encrypted EBS for
Postgres, Qdrant and uploads. Run exactly one API worker/replica because rate
limits and background workers are process-local. Start with resources appropriate
to CPU embedding and the corpus, then measure memory and ingestion latency before
choosing an instance size; no capacity or cost benchmark is claimed.

Put an Application Load Balancer with an ACM certificate in front of the web
port. Only the ALB security group may reach host port 3000; data services and the
API have no published ports. Use a private subnet with outbound connectivity to
the chosen provider and the model/image registries, and Session Manager for host
administration. Do not attach the development port overlay in AWS.

The prepared `compose.aws.yml` forces production mode and an external compatible
provider. Its web binding is intended for the restricted ALB-to-host connection;
it is not permission to expose an unauthenticated HTTP port to the internet.
Use `/api/readyz` as the ALB readiness health path, with a startup allowance for
embedding warmup; `/healthz` alone only checks nginx. Configure deregistration
and request timeouts to accommodate bounded agent/model requests. See the
[AWS target-group health-check reference](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/target-group-health-checks.html).

## Configuration prepared for the operator

Use `.env.compose.example` as a template and keep the real file private on the
host (mode 0600). Supply a unique URL-safe Postgres password and the provider key.
Use an instance role and Secrets Manager/SSM for retrieval; do not bake secrets
into an image, user-data script, browser bundle or git. Compose environment
variables are visible to users with Docker/host administration access. See
[AWS secret retrieval](https://docs.aws.amazon.com/secretsmanager/latest/userguide/retrieving-secrets.html).

Validate without starting or provisioning anything:

```sh
docker compose --env-file .env.compose -f docker-compose.yml -f compose.aws.yml config -q
```

Use `-q`: a full expanded Compose dump can reveal credentials. At release time,
build/promote tested images, record their digests, back up existing data and run
the same stack with the production overlay. Deployment remains an operator
action after credentials, networking, backups and review inputs are ready.
Changing the password variable on an existing Postgres volume does not rotate
its database password; perform database rotation deliberately.

## External generation

Both services use `LABDOCS_LLM_PROVIDER=openai_compatible`. The adapter sends
Bearer authentication and chat-completions requests, preserving opaque assistant
and tool-call protocol metadata. Each instance uses one configured provider;
comparison runs are separate evaluations, not silent failover.

| Setting | Groq | Gemini Developer API |
|---|---|---|
| `LABDOCS_LLM_BASE_URL` | `https://api.groq.com/openai/v1` | `https://generativelanguage.googleapis.com/v1beta/openai` |
| `LABDOCS_LLM_MODEL` | A tool-capable model enabled on the account; example `openai/gpt-oss-20b` | A compatible model enabled on the account; example `gemini-3.8-flash` |
| `LABDOCS_LLM_API_KEY` | Groq key | Gemini key |
| `LABDOCS_LLM_REASONING_EFFORT` | Optional `low` for a model that supports it | Optional `low`; model-dependent |

The endpoint formats and model examples were checked against the official docs
on 2026-10-26, not against a live authenticated account. Model availability,
limits and support can change. [Groq compatibility](https://console.groq.com/docs/openai)
and [model inventory](https://console.groq.com/docs/models) describe its current
interface; the client omits unsupported `messages[].name`.
[Gemini compatibility](https://ai.google.dev/gemini-api/docs/openai) documents the
endpoint and reasoning controls. Opaque `extra_content` is retained for protocol
roundtrips, including thought signatures; the
[Google adapter implementation](https://github.com/google/adk-java/blob/main/core/src/main/java/com/google/adk/models/chat/ChatCompletionsResponse.java)
also handles message-level signature metadata.

The template increases generation and judge output allowances for thinking
models. Tune these only after measuring valid JSON output, token usage and
latency. Agent step/total timeouts still apply; hidden reasoning may consume the
output allowance. Rate limits can trigger bounded retries. The gap admission
budget is conservative but cannot guarantee an arbitrary provider's billed
usage; set provider-side spend/quota limits separately.

Embeddings remain local BGE CPU inference. The first start downloads model
weights into the persistent cache; later starts reuse them. Ollama is an optional
development profile and is not a production dependency.

## Before deployment acceptance

- Exercise authenticated Search, Ask, Agent and Gap Check with the actual provider
  account on approved data. Mock tests establish protocol behavior only.
- Complete the [human-reviewed evaluation](../eval/README.md), including clean
  SOPs, verified mutations and exact-report false-positive reviews. Current
  candidate labels cannot establish quality or regulatory correctness.
- Protect API keys with TLS and a proper identity/session design for public use.
  The current paste-key/sessionStorage flow is a local-demo trade-off.
- Back up Postgres, Qdrant and uploads together; test restores. Qdrant can be
  rebuilt from canonical Postgres via `python -m app.cli reindex --backend qdrant`,
  but that command deletes/recreates the collection and requires a maintenance
  window. Never use `down -v` on data you intend to retain.
- Plan upgrades and interrupted-job handling. Jobs run in-process; a restart can
  strand a stored running job. There is no durable queue, automatic replay,
  multi-host replication or zero-downtime migration guarantee.
- Scrape metrics only inside the private network. Keep logs limited to IDs,
  lengths, status and timing; no API keys, raw documents or provider metadata.
