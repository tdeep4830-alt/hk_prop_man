import pytest
# 假設你的 Parser 儲存在 parser_module.py
from parser_module import ParentChildParser, ParentDocument, ChildNode

# --- 1. 準備測試數據 (Fixtures) ---
# 使用真實法例的 Edge Cases 來進行壓力測試
MOCK_TEXT_HAPPY_PATH = """
14. 法團的一般權力
(1) 除本條例另有規定外,法團會議可通過有關公用部分的決議。
(2) 在不損害第(1)款的概括性的原則下,法團可撤換委員。

15. 租客代表
(1) 認可組織的成員可委任一名佔用人為租客代表。
"""

MOCK_TEXT_NO_SUBSECTION = """
16. 獨立條文測試
這是一段沒有 (1), (2) 款項的純文字條文，測試 Parser 是否能安全處理。
"""

@pytest.fixture
def parser():
    """初始化 Parser 實例"""
    return ParentChildParser("Cap344")

# --- 2. 測試案例 (Test Cases) ---

def test_parent_document_creation(parser):
    """測試 Parent Document 是否準確生成及提取 Metadata"""
    parents, children = parser.parse(MOCK_TEXT_HAPPY_PATH)
    
    # 驗證 Parent 數量
    assert len(parents) == 2, "應該準確切出兩個 Section"
    
    # 驗證 ID 生成規範
    assert parents[0].id == "Cap344-S14"
    assert parents[1].id == "Cap344-S15"
    
    # 驗證 Title 提取 (極度重要，避免 Regex 炒車)
    assert parents[0].metadata["title"] == "法團的一般權力"
    assert parents[1].metadata["title"] == "租客代表"

def test_child_nodes_linkage(parser):
    """測試 Child Nodes 的 Parent-Child ID 綁定是否正確"""
    parents, children = parser.parse(MOCK_TEXT_HAPPY_PATH)
    
    # S14 有 2 款，S15 有 1 款，總共 3 個 Child
    assert len(children) == 3, "應該切出三個 Subsection Child Nodes"
    
    # 驗證 Foreign Key (parent_id) 綁定
    child_14_1 = children[0]
    assert child_14_1.id == "Cap344-S14-Sub1"
    assert child_14_1.parent_id == "Cap344-S14", "Child 必須準確指向對應的 Parent ID"
    
    child_15_1 = children[2]
    assert child_15_1.id == "Cap344-S15-Sub1"
    assert child_15_1.parent_id == "Cap344-S15"

def test_context_enrichment(parser):
    """測試 Context Enrichment (上下文注入) 是否按預期運作"""
    parents, children = parser.parse(MOCK_TEXT_HAPPY_PATH)
    
    child_content = children[0].content
    expected_prefix = "[Cap344 第 14 條 (法團的一般權力) - 第 (1) 款]"
    
    assert expected_prefix in child_content, "Child 內容必須包含自動注入的法例標題與條文號碼"
    assert "除本條例另有規定外" in child_content

def test_edge_case_no_subsection(parser):
    """邊緣測試：處理沒有 Subsections 的獨立條文"""
    parents, children = parser.parse(MOCK_TEXT_NO_SUBSECTION)
    
    assert len(parents) == 1
    assert parents[0].metadata["title"] == "獨立條文測試"
    
    # 如果沒有 (1), (2)，Parser 應該把整段文字當作一個 default child，或者保留在 Parent 中
    # 這裡確保 Parser 不會因為找不到 Regex match 而崩潰 (Crash)
    assert len(children) >= 0