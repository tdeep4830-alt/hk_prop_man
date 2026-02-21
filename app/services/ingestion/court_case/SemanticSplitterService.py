import re
from typing import List
from langchain_openai import ChatOpenAI
from langchain.schema import Document, SystemMessage, HumanMessage
from app.core.config import settings
import os

class SemanticSplitterService:
    def __init__(self):
        # 使用你藍圖中建議的 SiliconFlow (DeepSeek) 或 Groq
        self.llm = ChatOpenAI(
            model='deepseek-ai/DeepSeek-V3', 
            openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
            openai_api_base=os.getenv("DEEPSEEK_BASE_URL"),
            temperature=0  # 設為 0 以確保邊界識別的穩定性
        )

    async def detect_and_split(self, text: str, case_metadata: dict) -> List[Document]:
        """
        利用 LLM 偵測語義邊界並切割文檔
        """
        
        system_prompt = """
        你是一位香港法律專家。請閱讀以下法律判決書文本，並識別其邏輯結構的轉換點。
        請在每個邏輯段落（如：背景、雙方爭點、法律原則、法官判決）的起始位置插入標籤 [SECTION_BREAK]。
        不要修改原始文字，只需插入標籤。
        """

        # 為了節省 Token 並處理長文，建議將文本分成較大的塊（如 5000 字）處理
        # 這裡示範直接處理（假設判決書在 Context Window 內）
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"請標註以下文本的語義邊界：\n\n{text}")
        ]

        response = await self.llm.ainvoke(messages)
        tagged_text = response.content

        # 根據插入的標籤進行切割
        sections = re.split(r'\[SECTION_BREAK\]', tagged_text)
        
        documents = []
        for i, section_content in enumerate(sections):
            if not section_content.strip():
                continue
                
            # 建立 Parent Document
            doc = Document(
                page_content=section_content.strip(),
                metadata={
                    **case_metadata,
                    "section_index": i,
                    "segment_type": "semantic_parent"
                }
            )
            documents.append(doc)
            
        return documents


