from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PersonaProfile:
    persona_id: str
    label: str
    technical_level: str = "general"
    tone: str = "neutral"



PERSONA_PROFILES = {
    "NON_TECHNICAL_USER": PersonaProfile(
        "NON_TECHNICAL_USER",
        "Người dùng chưa rành kỹ thuật",
        "non_technical",
        "curious",
    ),
    "MANAGER": PersonaProfile(
        "MANAGER",
        "Quản lý",
        "business",
        "decision_oriented",
    ),
    "PURCHASING": PersonaProfile(
        "PURCHASING",
        "Mua sắm",
        "commercial",
        "precise",
    ),
    "IT_GENERALIST": PersonaProfile(
        "IT_GENERALIST",
        "IT tổng quát",
        "intermediate",
        "practical",
    ),
    "DEVELOPER": PersonaProfile(
        "DEVELOPER",
        "Lập trình viên",
        "technical",
        "direct",
    ),
    "ML_ENGINEER": PersonaProfile(
        "ML_ENGINEER",
        "Kỹ sư ML",
        "advanced",
        "precise",
    ),
    "SOLUTION_ARCHITECT": PersonaProfile(
        "SOLUTION_ARCHITECT",
        "Kiến trúc sư giải pháp",
        "advanced",
        "tradeoff_oriented",
    ),
}


def persona_for(index: int) -> PersonaProfile:
    names = tuple(PERSONA_PROFILES)
    return PERSONA_PROFILES[names[index % len(names)]]
