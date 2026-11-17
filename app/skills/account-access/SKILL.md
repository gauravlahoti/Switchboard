---
name: account-access
description: Fixes sign-in problems, meaning forgotten passwords, locked accounts and MFA questions. Use for password resets and lockouts. Do not use for permission requests, broken devices or software faults.
metadata:
  adk_additional_tools:
    - lookup_user
    - reset_password
    - search_kb
    - create_ticket
---

# Account access

## Procedure

1. If `lookup_user` is available, call it first. Note whether the account is locked and whether MFA is enrolled.
2. The person forgot their password or is locked out, and `reset_password` is available: call it once.
3. `reset_password` returns `mfa_required`: do not retry. Open a ticket for Identity and Access with `create_ticket`.
4. `reset_password` is not available to you: say you cannot reset it yourself, then open a ticket. If the person only asked how to reset a password, call `search_kb` with "password reset" and give the steps.
5. The account is already unlocked: say so and give the reset steps from `search_kb`.

## Rules

- Act only on the requester's own account. Never reset a password for someone else.
- Never repeat a reset link or code. Say the link was sent to the masked address.
- Never say an action happened unless a tool result confirms it.
- A question about how something works is answered, not acted on.
- Skip any step that needs a tool you were not given. Do not mention that it was skipped.

## Reply

Two to four short sentences: what you found, what you did, and what happens next. Mention a ticket id only if you created one.

If the person asks why a reset needs MFA or how long a link lasts, read `references/reset-policy.md` first.
