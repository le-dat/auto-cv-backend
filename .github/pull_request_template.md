## Summary

<!-- Briefly describe what this PR does and why -->

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Refactor
- [ ] Documentation
- [ ] Infrastructure (Docker Compose, CI, migrations)

## Areas Affected

- [ ] `app/api`
- [ ] `app/agents`
- [ ] `app/services`
- [ ] `app/models`
- [ ] `app/workers`
- [ ] `tests`
- [ ] `docs`
- [ ] `infra` (Dockerfile, Compose, CI)
- [ ] `knowledge` (Markdown guides)

## Related Issue

<!-- Link issue: Fixes #123 -->

## Migration Testing (if applicable)

<!-- For schema/model changes -->
- [ ] Migration tested locally with `alembic upgrade head`
- [ ] Downgrade path verified with `alembic downgrade -1`
- [ ] Data integrity checked after migration

## Technical Details

- [ ] Schema/Model changed (Pydantic, SQLAlchemy)
- [ ] Docker Compose config changed
- [ ] New environment variable added (update `.env.example`)
- [ ] New background task added (`arq`)
- [ ] New parsing/matching strategy added

## Testing

- [ ] `make test` passes locally
- [ ] Manual API testing (endpoints: `/api/v1/health`, `/api/v1/jobs`, `/api/v1/admin/faiss/build`, etc.)
- [ ] Background workers tested if affected

## Evidence (Optional)

<details>
<summary>Logs / Screenshots</summary>

<!-- Paste relevant output -->

</details>

## Backwards Compatibility

- [ ] API changes are backwards compatible (no breaking changes without deprecation)
- [ ] Database schema changes use additive migrations (no column removal without deprecation)

## Checklist

- [ ] `make lint` passes
- [ ] `make format` applied
- [ ] `make test` passes
- [ ] Project documentation updated if necessary
- [ ] `.env.example` updated if new env vars added
