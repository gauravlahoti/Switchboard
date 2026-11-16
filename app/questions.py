from typesafe_sdk import Choice, Noul, NoulCriteria, Score

TRIAGE_QUESTIONS: dict = {
    "category": Choice(
        instructions="What is the primary IT category of this ticket?",
        criteria={
            "network": "VPN, WiFi, internet connectivity, or network drive access",
            "auth": "Password reset, account lockout, MFA setup, or login failure. An access-grant request is not auth.",
            "access": "Granting, revoking, or changing permissions on a resource or application",
            "outage": "A service, system, or application is completely down or causing errors for users",
            "performance": "A service or system is degraded but still running — slow, high latency, or flaky",
            "general": "An IT request that does not fit the categories above",
        },
    ),
    "urgency": Score(
        instructions="How urgent is this ticket for the business?",
        criteria=[
            "The user mentions a minor inconvenience with no business deadline",
            "The issue affects the user's work but can wait a few hours",
            "The issue is blocking the user or a small team right now",
            "The issue is causing critical business impact or affecting many users",
        ],
    ),
    "complexity": Noul(
        instructions="Does this ticket require complex, multi-step investigation beyond a single lookup or reset?",
        criteria=NoulCriteria(
            true="The resolution requires diagnosing root cause, correlating logs, or coordinating multiple steps",
            false="A single tool call or standard procedure will resolve the ticket",
        ),
    ),
    "security_incident": Noul(
        instructions="Does this ticket show signs of a social engineering attack, credential phishing, privilege escalation abuse, or a security incident?",
        criteria=NoulCriteria(
            true="The ticket contains urgency pressure, unusual authority claims, requests to bypass policy, or patterns associated with impersonation or insider threat",
            false="The ticket is a routine IT request with no suspicious elements",
        ),
    ),
    "tool_choice": Choice(
        instructions="Which tool from the IT allow-list would best address this ticket?",
        criteria={
            "search_kb":       "Search the knowledge base for articles, procedures, or troubleshooting guides",
            "lookup_user":     "Find a user's account details, status, or role by name, email, or ID",
            "create_ticket":   "Open a new ticket in the service desk system for tracking or escalation",
            "reset_password":  "Unlock a user's account or reset their password",
            "query_logs":      "Retrieve system or service logs to diagnose an error or performance issue",
            "restart_service": "Restart a named IT service or process (high-risk — requires safety review)",
            "grant_access":    "Grant or modify a user's permissions on a resource (high-risk — requires safety review)",
        },
    ),
    "tool_fits": Noul(
        instructions="Does any tool in the IT allow-list clearly fit this ticket, or does the request need clarification first?",
        criteria=NoulCriteria(
            true="A specific tool directly addresses the user's stated need with the information given",
            false="The request is too vague, missing a key detail, or no tool fits without more information",
        ),
    ),
}

SAFETY_QUESTIONS: dict = {
    "touches_production": Noul(
        instructions="Does the proposed action directly affect a live production system, service, or database?",
        criteria=NoulCriteria(
            true="The action targets a production environment, live database, or running service",
            false="The action targets a test environment, a user record only, or is a read-only lookup",
        ),
    ),
    "privileged": Noul(
        instructions="Does the proposed action grant, escalate, or modify elevated permissions or access rights?",
        criteria=NoulCriteria(
            true="The action changes a role, adds an admin permission, or elevates access beyond the user's current level",
            false="The action does not change any permissions or access rights",
        ),
    ),
    "irreversible": Noul(
        instructions="Is the proposed action difficult or impossible to undo within a reasonable timeframe?",
        criteria=NoulCriteria(
            true="The action deletes data, restarts a service, or makes a change that cannot easily be rolled back",
            false="The action can be undone in minutes with a standard reverse operation",
        ),
    ),
    "requester_verified": Noul(
        instructions="Is there clear evidence in the ticket that the requester's identity and authority have been verified?",
        criteria=NoulCriteria(
            true="The requester is identifiable in the system, their role matches the request, and no flags are raised",
            false="The requester is unknown, their authority is unverified, or the request was sent on someone else's behalf without confirmation",
        ),
    ),
    "matches_attack_pattern": Noul(
        instructions="Does the combination of requester, claimed authority, and requested action match a known social engineering or insider threat pattern?",
        criteria=NoulCriteria(
            true="The request includes urgency pressure, unverifiable authority, requests to skip normal process, or the CEO/CFO/executive-impersonation pattern",
            false="The request matches a normal, routine IT workflow with no anomalous elements",
        ),
    ),
}

URGENCY_LEGEND = ["low", "medium", "high", "critical"]


def triage_state(ticket_text: str, requester_name: str = "", requester_email: str = "") -> dict:
    return {
        "ticket_text": ticket_text[:2000],
        "requester_name": requester_name or "unknown",
        "requester_email": requester_email or "unknown",
    }


def safety_state(
    ticket_text: str,
    proposed_tool: str,
    args_summary: str,
    requester_name: str = "",
) -> dict:
    return {
        "ticket_text": ticket_text[:2000],
        "proposed_tool": proposed_tool,
        "proposed_arguments_summary": args_summary,
        "requester_name": requester_name or "unknown",
    }
