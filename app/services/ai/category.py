"""Domain category classifier for Hong Kong building management queries.

Classifies user queries into one of 14 specific topic categories, enabling
category-specific retrieval filtering and tailored system prompt strategies.
"""

import enum

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from app.core.logger import logger
from app.services.ai.llm_provider import build_router_llm
from app.services.ai.prompts import CATEGORY_ROUTER_PROMPT


class Category(str, enum.Enum):
    BUILDING_MANAGEMENT_ORDINANCE = "building_management_ordinance"
    OWNERS_CORPORATION = "owners_corporation"
    FORMATION_OF_OWNERS_CORPORATION = "formation_of_owners_corporation"
    APPOINTMENT_OF_COMMITTEE_MEMBERS = "appointment_of_committee_members"
    MANAGEMENT_COMMITTEE = "management_committee"
    MEETINGS_OF_MANAGEMENT_COMMITTEE = "meetings_of_management_committee"
    FILLING_VACANCIES = "filling_vacancies"
    GENERAL_MEETINGS = "general_meetings"
    FINANCIAL_ARRANGEMENTS = "financial_arrangements"
    PROCUREMENT_ARRANGEMENTS = "procurement_arrangements"
    RESPONSIBILITIES_AND_RIGHTS_OF_OWNERS = "responsibilities_and_rights_of_owners"
    DUTIES_OF_MANAGER = "duties_of_manager"
    MANDATORY_BUILDING_MANAGEMENT = "mandatory_building_management"
    OTHER = "other"


# Human-readable labels for SSE / frontend display
CATEGORY_LABELS: dict[str, str] = {
    Category.BUILDING_MANAGEMENT_ORDINANCE: "Building Management Ordinance",
    Category.OWNERS_CORPORATION: "Owners' Corporation",
    Category.FORMATION_OF_OWNERS_CORPORATION: "Formation of an Owners' Corporation",
    Category.APPOINTMENT_OF_COMMITTEE_MEMBERS: "Appointment of Members of a Management Committee",
    Category.MANAGEMENT_COMMITTEE: "Management Committee",
    Category.MEETINGS_OF_MANAGEMENT_COMMITTEE: "Meetings of Management Committee",
    Category.FILLING_VACANCIES: "Filling Vacancies of a Management Committee",
    Category.GENERAL_MEETINGS: "General Meetings of Owners' Corporation",
    Category.FINANCIAL_ARRANGEMENTS: "Financial Arrangements for Owners' Corporation",
    Category.PROCUREMENT_ARRANGEMENTS: "Procurement Arrangements for Owners' Corporation",
    Category.RESPONSIBILITIES_AND_RIGHTS_OF_OWNERS: "Responsibilities and Rights of Owners",
    Category.DUTIES_OF_MANAGER: "Duties of Manager",
    Category.MANDATORY_BUILDING_MANAGEMENT: "Mandatory Building Management",
    Category.OTHER: "Other",
}

_VALID_CATEGORIES = {c.value for c in Category}

_category_prompt = PromptTemplate.from_template(CATEGORY_ROUTER_PROMPT)
_category_chain = _category_prompt | build_router_llm() | StrOutputParser()


class CategoryClassifier:
    """Classify a user query into one of 14 Hong Kong property management topic categories."""

    @staticmethod
    async def classify(query: str) -> Category:
        try:
            raw = await _category_chain.ainvoke({"query": query})
            category_str = raw.strip().lower()

            if category_str in _VALID_CATEGORIES:
                return Category(category_str)

            # Normalize: collapse multiple spaces/underscores, then try again
            normalized = "_".join(category_str.replace("-", "_").split())
            if normalized in _VALID_CATEGORIES:
                return Category(normalized)

            # Fuzzy fallback: find the valid category with the most character overlap
            best = max(_VALID_CATEGORIES, key=lambda v: sum(c in category_str for c in v))
            if len(best) > 0 and sum(c in category_str for c in best) / len(best) >= 0.85:
                return Category(best)

            logger.warning(
                "Category classifier returned unknown value", extra={"raw": raw}
            )
        except Exception as e:
            logger.warning(
                "Category classification failed", extra={"error": str(e)}
            )

        return Category.OTHER
