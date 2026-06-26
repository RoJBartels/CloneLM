"""The built-in local user.

Authentication is gated by ``DEPLOYED``: in the hosted build every request
carries a JWT for a real account, but localhost (the unchanged single-tenant dev
experience) has no login. To keep ONE data path — every notebook has an owner —
localhost requests resolve to this fixed, seeded user. It is created by the
0002 migration and backfilled onto any pre-existing notebooks.

In the deployed build this row simply sits unused: nobody can authenticate as it
(its password hash is a non-verifiable sentinel and registration requires a
unique email)."""
from __future__ import annotations

import uuid

# Fixed UUID so the migration seed, the FK backfill, and the runtime dependency
# all agree without a lookup.
LOCAL_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
LOCAL_USER_EMAIL = "local@localhost"
