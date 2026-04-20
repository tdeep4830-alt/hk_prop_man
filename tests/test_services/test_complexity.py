"""Unit tests for ComplexityClassifier — mocks LLM chain, no API calls."""

import pytest
from unittest.mock import AsyncMock

from app.services.ai.complexity import Complexity, ComplexityClassifier


@pytest.fixture
def mock_chain(mocker):
    mock = AsyncMock()
    mocker.patch("app.services.ai.complexity._complexity_chain", mock)
    return mock


class TestHappyPath:
    async def test_simple_routing(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="simple")
        result = await ComplexityClassifier.classify("你好")
        assert result == Complexity.SIMPLE

    async def test_medium_routing(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="medium")
        result = await ComplexityClassifier.classify("第344章第3條嘅定義係咩")
        assert result == Complexity.MEDIUM

    async def test_hard_routing(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="hard")
        result = await ComplexityClassifier.classify(
            "比較公契同第344章係爭議解決方面嘅分別，並分析業主大會決議可否凌駕公契條款"
        )
        assert result == Complexity.HARD

    async def test_uppercase_normalised(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="HARD")
        result = await ComplexityClassifier.classify("複雜問題")
        assert result == Complexity.HARD

    async def test_whitespace_stripped(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="  medium  ")
        result = await ComplexityClassifier.classify("點樣申請成立法團")
        assert result == Complexity.MEDIUM


class TestFallbackBehaviour:
    async def test_unknown_label_falls_back_to_medium(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="extreme")
        result = await ComplexityClassifier.classify("任何問題")
        assert result == Complexity.MEDIUM

    async def test_empty_response_falls_back_to_medium(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value="")
        result = await ComplexityClassifier.classify("任何問題")
        assert result == Complexity.MEDIUM

    async def test_exception_falls_back_to_medium(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(side_effect=Exception("LLM timeout"))
        result = await ComplexityClassifier.classify("任何問題")
        assert result == Complexity.MEDIUM

    async def test_network_error_falls_back_to_medium(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(side_effect=ConnectionError("network down"))
        result = await ComplexityClassifier.classify("任何問題")
        assert result == Complexity.MEDIUM

    async def test_json_garbage_falls_back_to_medium(self, mock_chain):
        mock_chain.ainvoke = AsyncMock(return_value='{"complexity": "hard"}')
        result = await ComplexityClassifier.classify("任何問題")
        assert result == Complexity.MEDIUM


class TestComplexityEnum:
    def test_all_values_defined(self):
        assert Complexity.SIMPLE.value == "simple"
        assert Complexity.MEDIUM.value == "medium"
        assert Complexity.HARD.value == "hard"

    def test_is_str_enum(self):
        assert Complexity.SIMPLE == "simple"
        assert Complexity.MEDIUM == "medium"
        assert Complexity.HARD == "hard"
