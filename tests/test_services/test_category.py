"""Unit tests for CategoryClassifier — mocks LLM chain, no API calls."""

import pytest
from unittest.mock import AsyncMock

from app.services.ai.category import Category, CategoryClassifier, CATEGORY_LABELS


@pytest.fixture
def mock_chain(mocker):
    mock = AsyncMock()
    mocker.patch("app.services.ai.category._category_chain", mock)
    return mock


class TestHappyPath:
    async def test_building_management_ordinance(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="building_management_ordinance")
        result = await CategoryClassifier.classify("第344章第3條點樣定義業主")
        assert result == Category.BUILDING_MANAGEMENT_ORDINANCE

    async def test_owners_corporation(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="owners_corporation")
        result = await CategoryClassifier.classify("業主立案法團有冇法人資格")
        assert result == Category.OWNERS_CORPORATION

    async def test_formation_of_owners_corporation(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="formation_of_owners_corporation")
        result = await CategoryClassifier.classify("點樣成立業主立案法團")
        assert result == Category.FORMATION_OF_OWNERS_CORPORATION

    async def test_appointment_of_committee_members(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="appointment_of_committee_members")
        result = await CategoryClassifier.classify("管委會成員可唔可以係租客")
        assert result == Category.APPOINTMENT_OF_COMMITTEE_MEMBERS

    async def test_management_committee(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="management_committee")
        result = await CategoryClassifier.classify("管委會有咩權力")
        assert result == Category.MANAGEMENT_COMMITTEE

    async def test_meetings_of_management_committee(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="meetings_of_management_committee")
        result = await CategoryClassifier.classify("管委會會議法定人數係幾多")
        assert result == Category.MEETINGS_OF_MANAGEMENT_COMMITTEE

    async def test_filling_vacancies(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="filling_vacancies")
        result = await CategoryClassifier.classify("管委會主席辭職後點辦")
        assert result == Category.FILLING_VACANCIES

    async def test_general_meetings(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="general_meetings")
        result = await CategoryClassifier.classify("業主大會決議需要幾多票通過")
        assert result == Category.GENERAL_MEETINGS

    async def test_financial_arrangements(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="financial_arrangements")
        result = await CategoryClassifier.classify("儲備基金最少要保留幾多錢")
        assert result == Category.FINANCIAL_ARRANGEMENTS

    async def test_procurement_arrangements(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="procurement_arrangements")
        result = await CategoryClassifier.classify("法團採購工程要唔要招標")
        assert result == Category.PROCUREMENT_ARRANGEMENTS

    async def test_responsibilities_and_rights_of_owners(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="responsibilities_and_rights_of_owners")
        result = await CategoryClassifier.classify("業主可唔可以拒絕俾管理費")
        assert result == Category.RESPONSIBILITIES_AND_RIGHTS_OF_OWNERS

    async def test_duties_of_manager(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="duties_of_manager")
        result = await CategoryClassifier.classify("管理公司有咩法定責任")
        assert result == Category.DUTIES_OF_MANAGER

    async def test_mandatory_building_management(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="mandatory_building_management")
        result = await CategoryClassifier.classify("政府幾時可以發強制樓宇管理令")
        assert result == Category.MANDATORY_BUILDING_MANAGEMENT

    async def test_other(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="other")
        result = await CategoryClassifier.classify("附近有新商場開")
        assert result == Category.OTHER

    async def test_uppercase_normalised(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="GENERAL_MEETINGS")
        result = await CategoryClassifier.classify("業主大會")
        assert result == Category.GENERAL_MEETINGS

    async def test_whitespace_stripped(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="  financial_arrangements  ")
        result = await CategoryClassifier.classify("管理費問題")
        assert result == Category.FINANCIAL_ARRANGEMENTS


class TestFallbackBehaviour:
    async def test_unknown_label_falls_back_to_other(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="unknown_topic")
        result = await CategoryClassifier.classify("任何問題")
        assert result == Category.OTHER

    async def test_empty_response_falls_back_to_other(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="")
        result = await CategoryClassifier.classify("任何問題")
        assert result == Category.OTHER

    async def test_exception_falls_back_to_other(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(side_effect=Exception("LLM timeout"))
        result = await CategoryClassifier.classify("任何問題")
        assert result == Category.OTHER

    async def test_network_error_falls_back_to_other(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(side_effect=ConnectionError("network down"))
        result = await CategoryClassifier.classify("任何問題")
        assert result == Category.OTHER

    async def test_json_garbage_falls_back_to_other(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value='{"category": "financial_arrangements"}')
        result = await CategoryClassifier.classify("任何問題")
        assert result == Category.OTHER


class TestCategoryEnum:
    def test_all_14_categories_defined(self):
        assert len(Category) == 14

    def test_all_categories_have_labels(self):
        for cat in Category:
            assert cat in CATEGORY_LABELS
            assert isinstance(CATEGORY_LABELS[cat], str)
            assert len(CATEGORY_LABELS[cat]) > 0

    def test_is_str_enum(self):
        assert Category.BUILDING_MANAGEMENT_ORDINANCE == "building_management_ordinance"
        assert Category.OWNERS_CORPORATION == "owners_corporation"
        assert Category.OTHER == "other"

    def test_label_values_match_spec(self):
        assert CATEGORY_LABELS[Category.BUILDING_MANAGEMENT_ORDINANCE] == "Building Management Ordinance"
        assert CATEGORY_LABELS[Category.OWNERS_CORPORATION] == "Owners' Corporation"
        assert CATEGORY_LABELS[Category.FORMATION_OF_OWNERS_CORPORATION] == "Formation of an Owners' Corporation"
        assert CATEGORY_LABELS[Category.APPOINTMENT_OF_COMMITTEE_MEMBERS] == "Appointment of Members of a Management Committee"
        assert CATEGORY_LABELS[Category.MANAGEMENT_COMMITTEE] == "Management Committee"
        assert CATEGORY_LABELS[Category.MEETINGS_OF_MANAGEMENT_COMMITTEE] == "Meetings of Management Committee"
        assert CATEGORY_LABELS[Category.FILLING_VACANCIES] == "Filling Vacancies of a Management Committee"
        assert CATEGORY_LABELS[Category.GENERAL_MEETINGS] == "General Meetings of Owners' Corporation"
        assert CATEGORY_LABELS[Category.FINANCIAL_ARRANGEMENTS] == "Financial Arrangements for Owners' Corporation"
        assert CATEGORY_LABELS[Category.PROCUREMENT_ARRANGEMENTS] == "Procurement Arrangements for Owners' Corporation"
        assert CATEGORY_LABELS[Category.RESPONSIBILITIES_AND_RIGHTS_OF_OWNERS] == "Responsibilities and Rights of Owners"
        assert CATEGORY_LABELS[Category.DUTIES_OF_MANAGER] == "Duties of Manager"
        assert CATEGORY_LABELS[Category.MANDATORY_BUILDING_MANAGEMENT] == "Mandatory Building Management"
        assert CATEGORY_LABELS[Category.OTHER] == "Other"
