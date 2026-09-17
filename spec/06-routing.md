# Deterministic Routing RC0

Routing is intentionally transparent:

1. parse required capabilities/interfaces/modalities;
2. eliminate ineligible executors;
3. eliminate disabled or unverified executors;
4. apply security/project constraints;
5. apply explicit ordered preference;
6. consult runtime availability;
7. select the first eligible preferred executor;
8. try ordered fallbacks;
9. return `BLOCKED_NO_VERIFIED_EXECUTOR` if none qualify.

RC0 performs no learned scoring and invokes no model.
