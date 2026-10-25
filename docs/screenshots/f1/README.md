# F1 final screenshots

Real Chromium captures from the native Vite/proxy layout, light mode at 1280,
390 and 360px and the requested dark states. All routes wait for actual content;
the spec asserts no horizontal page overflow. Device scale is 1. These are the
final captures, not mockups or intermediate design variants.

The API uses an isolated `_test` database/collection, real auth/readiness routes
and the fake provider. The library and completed gap job are labelled synthetic
fixtures. The shared-error screen injects a deterministic 502 response in the
browser; it is not a live local-model failure. Password inputs mask test keys.

| Route / state | 1280px | 390px | 360px |
| --- | --- | --- | --- |
| Shell / Ask | [Light](ask-light-1280.png) | [Light](ask-light-390.png) | [Light](ask-light-360.png) |
| Search | [Light](search-light-1280.png) | [Light](search-light-390.png) | [Light](search-light-360.png) |
| Agent | [Light](agent-light-1280.png) | [Light](agent-light-390.png) | [Light](agent-light-360.png) |
| Gap input | [Light](gap-check-light-1280.png) | [Light](gap-check-light-390.png) | [Light](gap-check-light-360.png) |
| Gap job URL | [Light](gap-job-light-1280.png) | [Light](gap-job-light-390.png) | [Light](gap-job-light-360.png) |
| Documents | [Light](documents-light-1280.png) | [Light](documents-light-390.png) | [Light](documents-light-360.png) |
| Settings / valid | [Light](settings-valid-light-1280.png) | [Light](settings-valid-light-390.png) | [Light](settings-valid-light-360.png) |
| Settings / invalid key | [Light](settings-invalid-light-1280.png) | [Light](settings-invalid-light-390.png) | — |
| Settings / read-only key | [Light](settings-read-only-light-1280.png) | [Light](settings-read-only-light-390.png) | — |
| Shared 502 error fixture | [Light](shared-error-light-1280.png) | [Light](shared-error-light-390.png) | — |
| Shell / Ask | [Dark](ask-dark-1280.png) | [Dark](ask-dark-390.png) | — |
| Settings / valid | [Dark](settings-valid-dark-1280.png) | [Dark](settings-valid-dark-390.png) | — |

[F1 review summary](../../frontend-f1-review.md).
