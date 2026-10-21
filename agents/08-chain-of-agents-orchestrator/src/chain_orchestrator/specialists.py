"""Bounded local transformations, with no services, tools, writes, or successors.

Each specialist proposes one claim per assigned record. The release role also
proposes a catalogue; the manager independently checks both before acceptance.
"""

import asyncio

from .contracts import Claim, Findings, Reference, ReleaseFindings, Reply, Request, Role


async def specialize(request: Request) -> Reply:
    """Yield cooperatively, then transform only this role's immutable records."""
    await asyncio.sleep(0)
    claims = tuple(
        Claim(request.recipient, record.scope, record.works,
              Reference(record.source_id, record.record_id, request.snapshot_sha256))
        for record in request.records
    )
    if request.recipient is Role.RELEASE:
        payload = ReleaseFindings(tuple(sorted({c.scope.feature_id for c in claims})), claims)
    else:
        payload = Findings(claims)
    return Reply(request.run_id, request.task_id, request.recipient, "manager", payload)
