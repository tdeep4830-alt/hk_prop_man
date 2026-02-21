"""Unit tests for SemanticRouter — mocks LLM chain, no API calls required."""

import pytest
from unittest.mock import AsyncMock

from app.services.ai.router import Intent, SemanticRouter


@pytest.fixture
def mock_chain(mocker):
    """Patch the module-level _router_chain with an AsyncMock."""
    mock = AsyncMock()
    mocker.patch("app.services.ai.router._router_chain", mock)
    return mock


class TestHappyPath:
    """LLM returns valid intent strings."""

    async def test_legal_definition_routing(self, mock_chain):
        """LLM 返回 'legal_definition' → Intent.LEGAL_DEFINITION。"""
        mock_chain.ainvoke = AsyncMock(return_value="legal_definition")
        intent = await SemanticRouter.classify("業主立案法團定義係咩")
        assert intent == Intent.LEGAL_DEFINITION

    async def test_sop_procedure_routing(self, mock_chain):
        """LLM 返回 'sop_procedure' → Intent.SOP_PROCEDURE。"""
        mock_chain.ainvoke = AsyncMock(return_value="sop_procedure")
        intent = await SemanticRouter.classify("點樣成立業主立案法團")
        assert intent == Intent.SOP_PROCEDURE

    async def test_dispute_routing(self, mock_chain):
        """LLM 返回 'dispute' → Intent.DISPUTE。"""
        mock_chain.ainvoke = AsyncMock(return_value="dispute")
        intent = await SemanticRouter.classify("管理公司拒絕提供賬目")
        assert intent == Intent.DISPUTE

    async def test_uppercase_output_normalised(self, mock_chain):
        """LLM 返回大寫 'LEGAL_DEFINITION' → 應 lowercase 後匹配，返回 LEGAL_DEFINITION。"""
        mock_chain.ainvoke = AsyncMock(return_value="LEGAL_DEFINITION")
        intent = await SemanticRouter.classify("法律定義問題")
        assert intent == Intent.LEGAL_DEFINITION

    async def test_intent_with_whitespace(self, mock_chain):
        """LLM 返回帶空格的 intent 字串 → strip 後應正常匹配。"""
        mock_chain.ainvoke = AsyncMock(return_value="  sop_procedure  ")
        intent = await SemanticRouter.classify("成立法團程序")
        assert intent == Intent.SOP_PROCEDURE


class TestFallbackBehaviour:
    """Invalid LLM responses and exceptions fall back to LEGAL_DEFINITION."""

    async def test_unknown_intent_fallback(self, mock_chain):
        """LLM 返回未知 intent 字串 → 降級為 LEGAL_DEFINITION。"""
        mock_chain.ainvoke = AsyncMock(return_value="unknown_intent")
        intent = await SemanticRouter.classify("隨便問題")
        assert intent == Intent.LEGAL_DEFINITION

    async def test_empty_response_fallback(self, mock_chain):
        """LLM 返回空字串 → 降級為 LEGAL_DEFINITION。"""
        mock_chain.ainvoke = AsyncMock(return_value="")
        intent = await SemanticRouter.classify("任何問題")
        assert intent == Intent.LEGAL_DEFINITION

    async def test_exception_fallback(self, mock_chain):
        """LLM 拋出異常 → 降級為 LEGAL_DEFINITION，不 raise。"""
        mock_chain.ainvoke = AsyncMock(side_effect=Exception("LLM timeout"))
        intent = await SemanticRouter.classify("任何問題")
        assert intent == Intent.LEGAL_DEFINITION

    async def test_network_error_fallback(self, mock_chain):
        """網絡錯誤 → 降級為 LEGAL_DEFINITION。"""
        mock_chain.ainvoke = AsyncMock(side_effect=ConnectionError("network error"))
        intent = await SemanticRouter.classify("網絡問題測試")
        assert intent == Intent.LEGAL_DEFINITION

    async def test_garbage_output_fallback(self, mock_chain):
        """LLM 返回垃圾輸出（含 JSON、markdown）→ 降級為 LEGAL_DEFINITION。"""
        mock_chain.ainvoke = AsyncMock(return_value='{"intent": "dispute"}')
        intent = await SemanticRouter.classify("混亂輸出測試")
        assert intent == Intent.LEGAL_DEFINITION


class TestIntentEnum:
    """Validate Intent enum values and structure."""

    def test_all_intents_defined(self):
        """三個 Intent 值應存在。"""
        assert Intent.LEGAL_DEFINITION.value == "legal_definition"
        assert Intent.SOP_PROCEDURE.value == "sop_procedure"
        assert Intent.DISPUTE.value == "dispute"

    def test_intent_is_str_enum(self):
        """Intent 應是 str enum，可直接作字串比較。"""
        assert Intent.LEGAL_DEFINITION == "legal_definition"
        assert Intent.SOP_PROCEDURE == "sop_procedure"
        assert Intent.DISPUTE == "dispute"
