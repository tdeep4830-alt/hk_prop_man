"""Unit tests for PIIMaskingService — no DB, no LLM, no external dependencies."""

import pytest

from app.services.ai.pii_masking import PIIMaskingService


class TestHKIDMasking:
    """HKID number detection and masking."""

    def test_single_letter_hkid(self):
        """標準單字母 HKID (A123456(0)) 應被替換。"""
        result = PIIMaskingService.mask("業主 A123456(0) 投訴")
        assert result.masked_text == "業主 [HKID] 投訴"
        assert any(p["type"] == "HKID" for p in result.pii_found)

    def test_double_letter_hkid(self):
        """雙字母 HKID (AB123456(7)) 應被替換。"""
        result = PIIMaskingService.mask("AB123456(7) 係負責人")
        assert result.masked_text == "[HKID] 係負責人"
        assert any(p["type"] == "HKID" for p in result.pii_found)

    def test_hkid_check_digit_a(self):
        """HKID check digit 可以係字母 A。"""
        result = PIIMaskingService.mask("持有人 C987654(A)")
        assert "[HKID]" in result.masked_text
        assert any(p["type"] == "HKID" for p in result.pii_found)

    def test_invalid_id_too_short(self):
        """不足位數的 ID (A12345，只有 5 位) 不應替換。"""
        result = PIIMaskingService.mask("案件 A12345")
        assert result.masked_text == "案件 A12345"
        assert not any(p["type"] == "HKID" for p in result.pii_found)

    def test_invalid_id_no_check_digit(self):
        """沒有括號 check digit 的 ID 不應替換。"""
        result = PIIMaskingService.mask("參考號 A1234567")
        assert "HKID" not in result.masked_text.upper() or "[HKID]" not in result.masked_text
        # Should not match as HKID (no parenthesis check digit)
        assert not any(p["type"] == "HKID" for p in result.pii_found)


class TestPhoneMasking:
    """Hong Kong phone number detection and masking."""

    def test_phone_9x_prefix(self):
        """9x 開頭香港電話應被替換。"""
        result = PIIMaskingService.mask("致電 91234567 查詢")
        assert result.masked_text == "致電 [PHONE] 查詢"
        assert any(p["type"] == "PHONE" for p in result.pii_found)

    def test_phone_5x_prefix(self):
        """5x 開頭香港電話應被替換。"""
        result = PIIMaskingService.mask("WhatsApp 51234567")
        assert result.masked_text == "WhatsApp [PHONE]"
        assert any(p["type"] == "PHONE" for p in result.pii_found)

    def test_phone_6x_prefix(self):
        """6x 開頭香港電話應被替換。"""
        result = PIIMaskingService.mask("聯絡 61234567 預約")
        assert result.masked_text == "聯絡 [PHONE] 預約"
        assert any(p["type"] == "PHONE" for p in result.pii_found)

    def test_phone_8x_prefix(self):
        """8x 開頭香港電話應被替換。"""
        result = PIIMaskingService.mask("熱線 81234567")
        assert result.masked_text == "熱線 [PHONE]"
        assert any(p["type"] == "PHONE" for p in result.pii_found)

    def test_non_hk_phone_1x_prefix(self):
        """1 開頭號碼不應被替換（非香港電話格式）。"""
        result = PIIMaskingService.mask("12345678")
        assert result.masked_text == "12345678"
        assert not any(p["type"] == "PHONE" for p in result.pii_found)

    def test_non_hk_phone_2x_prefix(self):
        """2 開頭號碼不應被替換（非手提電話）。"""
        result = PIIMaskingService.mask("聯絡 21234567")
        assert "PHONE" not in result.masked_text
        assert not any(p["type"] == "PHONE" for p in result.pii_found)


class TestUnitAddressMasking:
    """Hong Kong unit address detection and masking."""

    def test_standard_unit_address(self):
        """標準座樓室地址應被替換。"""
        result = PIIMaskingService.mask("投訴人住 3座12樓B室")
        assert result.masked_text == "投訴人住 [UNIT_REDACTED]"
        assert any(p["type"] == "UNIT_ADDRESS" for p in result.pii_found)

    def test_single_digit_floor(self):
        """單位數樓層地址應被替換。"""
        result = PIIMaskingService.mask("業主 1座2樓A室 提出申請")
        assert "[UNIT_REDACTED]" in result.masked_text
        assert any(p["type"] == "UNIT_ADDRESS" for p in result.pii_found)


class TestMultiplePII:
    """Multiple PII in same text."""

    def test_all_pii_types_replaced(self):
        """含 HKID + 地址 + 電話的文字，三者均應被替換。"""
        text = "A123456(0) 住 1座2樓A室 電話 98765432"
        result = PIIMaskingService.mask(text)
        assert "[HKID]" in result.masked_text
        assert "[UNIT_REDACTED]" in result.masked_text
        assert "[PHONE]" in result.masked_text
        pii_types = {p["type"] for p in result.pii_found}
        assert "HKID" in pii_types
        assert "UNIT_ADDRESS" in pii_types
        assert "PHONE" in pii_types

    def test_two_phones_in_text(self):
        """文字中兩個電話號碼都應被替換。"""
        result = PIIMaskingService.mask("主線 91234567，備用 51234568")
        assert result.masked_text == "主線 [PHONE]，備用 [PHONE]"
        phone_items = [p for p in result.pii_found if p["type"] == "PHONE"]
        assert len(phone_items) == 2


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_string(self):
        """空字串應返回空字串，pii_found 為空。"""
        result = PIIMaskingService.mask("")
        assert result.masked_text == ""
        assert result.pii_found == []

    def test_no_pii_text(self):
        """無 PII 的文字應原文返回，pii_found 為空。"""
        text = "業主大會決議通過管理費加幅"
        result = PIIMaskingService.mask(text)
        assert result.masked_text == text
        assert result.pii_found == []

    def test_pii_found_structure(self):
        """pii_found 每個項目應包含 type, start, end 欄位。"""
        result = PIIMaskingService.mask("A123456(0) 查詢")
        assert len(result.pii_found) >= 1
        item = result.pii_found[0]
        assert "type" in item
        assert "start" in item
        assert "end" in item
        assert isinstance(item["start"], int)
        assert isinstance(item["end"], int)

    def test_mask_result_type(self):
        """返回值應為 MaskResult，含 masked_text 及 pii_found 屬性。"""
        from app.services.ai.pii_masking import MaskResult
        result = PIIMaskingService.mask("測試")
        assert isinstance(result, MaskResult)
        assert hasattr(result, "masked_text")
        assert hasattr(result, "pii_found")
