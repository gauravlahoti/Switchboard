from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.store import store

POLICY_PATH = Path(__file__).parent / "policy.toml"
SELF, ANY = "self", "any"


class UnknownProfile(KeyError):
    pass


class Requester(BaseModel):
    profile: str
    label: str
    title: str
    user_id: str
    name: str
    email: str
    department: str
    role: str
    tools: list[str]
    scope: dict[str, str]

    @property
    def first_name(self) -> str:
        return self.name.split()[0] if self.name.strip() else self.label

    def can_use(self, tool: str) -> bool:
        return tool in self.tools


@lru_cache(maxsize=1)
def policy() -> dict[str, Any]:
    with POLICY_PATH.open("rb") as fh:
        data = tomllib.load(fh)
    for pid, prof in data["profiles"].items():
        for tool in prof["tools"]:
            if tool not in prof.get("scope", {}):
                raise ValueError(f"profile {pid}: tool {tool!r} has no scope")
        if prof["scope"].get("reset_password", SELF) != SELF:
            raise ValueError(f"profile {pid}: reset_password may only act on self")
    for tool, who in data.get("safety", {}).get("approvers", {}).items():
        for pid in who:
            if pid not in data["profiles"]:
                raise ValueError(f"approver {pid!r} for {tool} is not a profile")
    return data


def approvers_for(tool: str, requester_profile: str) -> list[dict[str, str]]:
    """Profiles that may approve this tool for this requester. Nobody approves their own request."""
    allowed = policy().get("safety", {}).get("approvers", {}).get(tool, [])
    profiles = policy()["profiles"]
    return [
        {"id": pid, "label": profiles[pid]["label"], "title": profiles[pid]["title"]}
        for pid in allowed
        if pid != requester_profile
    ]


def resolve(profile_id: str) -> Requester:
    prof = policy()["profiles"].get(profile_id)
    if prof is None:
        raise UnknownProfile(profile_id)
    person = store.get_user(prof["person"])
    if person is None:
        raise ValueError(f"profile {profile_id}: person {prof['person']!r} not in the directory")
    return Requester(
        profile=profile_id,
        label=prof["label"],
        title=prof["title"],
        user_id=person["id"],
        name=person["name"],
        email=person["email"],
        department=person["department"],
        role=person["role"],
        tools=list(prof["tools"]),
        scope=dict(prof["scope"]),
    )


def catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": pid,
            "label": prof["label"],
            "title": prof["title"],
            "approves": sorted(
                t for t, who in policy().get("safety", {}).get("approvers", {}).items() if pid in who
            ),
            "tools": [
                {"name": t, "scope": prof["scope"][t]} for t in prof["tools"]
            ],
        }
        for pid, prof in policy()["profiles"].items()
    ]
