# FastAPI adapter instructions

These rules apply under `apps/api/` in addition to the repository instructions.

- Keep routes thin: validate transport input, resolve authentication, call an application use case, and translate the result.
- Domain decisions and authorization rules belong in backend application/domain code.
- Do not perform expensive or unsafe PDF processing inside the API process.
- Reuse shared response/error conventions and avoid leaking infrastructure exceptions.
- A public API change requires relevant success, validation, authorization, and error-path tests.
- Regenerate frontend OpenAPI types with `make web-api-types` after intentional contract changes; never edit `apps/web/src/api/schema.d.ts` manually.

During implementation, run the affected test file or node first, for example:

~~~bash
uv run --locked pytest apps/api/tests/test_health.py -q
uv run --locked ruff check apps/api
~~~

Broaden to API tests, type checking, and `make web-api-types-check` only when the affected boundary requires them.
