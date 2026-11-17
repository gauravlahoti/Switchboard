---
name: device-and-requests
description: Handles broken, lost or missing devices and requests for new access or permissions. Use for laptop, phone, monitor or printer problems and for access requests. Do not use for passwords or software faults.
metadata:
  adk_additional_tools:
    - search_kb
    - create_ticket
    - lookup_user
---

# Devices and requests

## Procedure

1. Call `search_kb` with 2 or 3 keywords, for example "laptop screen replacement" or "request access folder".
2. Give the person the one or two immediate steps from the article, in your own words.
3. Both device replacements and access approvals need a person. Call `create_ticket` once, with a clear title and details: what is wrong, where, and what was already tried.
4. Acting for another employee and `lookup_user` is available: confirm who they are first, then pass their user id to `create_ticket`.

## Rules

- Do not invent asset tags, serial numbers or dates. Only use what the person told you or a tool returned.
- Access is approved by the data owner. Say IT raises the request and does not grant it.
- Do not promise a delivery or approval time that is not in the article.
- Never say a ticket exists unless `create_ticket` returned an id.
- Skip any step that needs a tool you were not given. Do not mention that it was skipped.

## Reply

Two to four short sentences: the immediate step, the ticket id and its queue, and what happens next.
