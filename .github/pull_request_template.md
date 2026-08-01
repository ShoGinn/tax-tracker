## Summary

- Describe the change and why it is needed.

## Validation

- [ ] `just check` (or equivalent targeted checks) was run successfully
- [ ] Relevant unit/integration tests were added or updated
- [ ] Examples, fixtures, screenshots, and logs use synthetic data and contain no credentials or personally identifiable information

## Tax Logic Review Checklist

- [ ] For tax-calculation numeric assertions, expected values come from IRS/SSA-backed fixtures or are explicitly derived from loaded tax models (not opaque literals)
- [ ] Any intentionally synthetic numeric test data is labeled with a short rationale
- [ ] Tax data or behavior changes are reflected in docs (`README.md` and/or `docs/`)
- [ ] Authoritative IRS/SSA sources are linked for tax-data or calculation changes

## Risk and Impact

- Note any user-facing, privacy, security, compatibility, or deployment impact.
