# PR29 implementation notes

The Operations frontend calls existing API routes only. Authorization remains enforced server-side; UI role checks are an additional presentation guard, not the security boundary.

The Integration Center architecture correction is intentionally isolated as a compatibility layer so the large Phase 24 integration module is not broadly rewritten during this safety-focused change. A later frontend consolidation can remove the compatibility layer when Phase 24 is refactored.
