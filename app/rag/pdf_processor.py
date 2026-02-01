# app/rag/pdf_processor.py - COMPLETE FIXED VERSION

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
# from langchain_huggingface import HuggingFaceEmbeddings

from langchain_community.vectorstores import FAISS
from typing import List, Optional
import os
from app.logg import logger
from app.config import get_settings

from google import genai
from langchain.embeddings.base import Embeddings
from typing import List

settings = get_settings()
class GoogleGenAIEmbeddings(Embeddings):
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents"""


        embeddings = []
        for text in texts:
            result = self.client.models.embed_content(
                model="gemini-embedding-001",
                contents=text
            )
            embeddings.append(result.embeddings[0].values)
        return embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query"""
        result = self.client.models.embed_content(
            model="gemini-embedding-001",
            contents=text
        )
        return result.embeddings[0].values


class PDFProcessor:
    def __init__(self, persist_directory: str = "./faiss_db"):
        self.persist_directory = persist_directory
        os.makedirs(persist_directory, exist_ok=True)
        
        logger.info(f"🔧 Initializing PDFProcessor with directory: {persist_directory}")

        # self.embeddings = HuggingFaceEmbeddings(
        #     model_name="sentence-transformers/all-mpnet-base-v2"
        # )
        # Then in your PDFProcessor __init__:
        self.embeddings = GoogleGenAIEmbeddings(
            api_key=settings.GOOGLE_API_KEY
        )

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )
        
        logger.info("✅ PDFProcessor initialized successfully")

    def load_pdf(self, pdf_path: str):
        """Load PDF using PyPDFLoader"""
        try:
            logger.info(f"📄 Loading PDF: {pdf_path}")
            loader = PyPDFLoader(pdf_path)
            documents = loader.load()
            logger.info(f"✅ Loaded {len(documents)} pages from PDF")
            return documents
        except Exception as e:
            logger.exception(f"❌ Error loading PDF: {e}")
            raise Exception(f"Error loading PDF: {str(e)}")

    def process_pdf(self, pdf_path: str, user_id: int, doc_id: int) -> bool:
        """Process PDF and store in user-specific FAISS index"""
        try:
            logger.info("=" * 60)
            logger.info(f"🧠 PROCESSING PDF")
            logger.info(f"   User ID: {user_id}")
            logger.info(f"   Doc ID: {doc_id}")
            logger.info(f"   Path: {pdf_path}")
            
            # 1. Load PDF
            documents = self.load_pdf(pdf_path)
            if not documents:
                raise Exception("No content found in PDF")

            # 2. Add metadata
            for i, doc in enumerate(documents):
                doc.metadata.update({
                    "user_id": user_id,
                    "doc_id": doc_id,
                    "source": os.path.basename(pdf_path),
                    "page": doc.metadata.get("page", i + 1),  # Page numbers start at 1
                })

            # 3. Split into chunks
            logger.info("✂️  Splitting documents into chunks...")
            chunks = self.text_splitter.split_documents(documents)
            logger.info(f"✅ Created {len(chunks)} chunks")

            # 4. User-specific FAISS path
            user_db_path = os.path.join(self.persist_directory, f"user_{user_id}")
            logger.info(f"📁 Vector store path: {user_db_path}")

            # 5. Load or create vector store
            if os.path.exists(user_db_path):
                logger.info("📂 Loading existing vector store...")
                vectorstore = FAISS.load_local(
                    user_db_path,
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                logger.info("➕ Adding new documents to existing store...")
                vectorstore.add_documents(chunks)
            else:
                logger.info("🆕 Creating new vector store...")
                vectorstore = FAISS.from_documents(
                    documents=chunks,
                    embedding=self.embeddings
                )

            # 6. Save
            logger.info("💾 Saving vector store...")
            vectorstore.save_local(user_db_path)
            
            logger.info("=" * 60)
            logger.info(f"✅ PDF PROCESSING COMPLETE")
            logger.info("=" * 60)
            
            return True

        except Exception as e:
            logger.exception(f"❌ Error processing PDF: {e}")
            raise Exception(f"Error processing PDF: {str(e)}")

    def get_vectorstore(self, user_id: int) -> Optional[FAISS]:
        """Load user's vector store"""
        user_db_path = os.path.join(self.persist_directory, f"user_{user_id}")

        if not os.path.exists(user_db_path):
            logger.warning(f"📭 No vector store found for user {user_id} at {user_db_path}")
            return None

        try:
            logger.info(f"📂 Loading vector store for user {user_id}")
            vectorstore = FAISS.load_local(
                user_db_path,
                self.embeddings,
                allow_dangerous_deserialization=True
            )
            logger.info(f"✅ Vector store loaded successfully")
            return vectorstore
        except Exception as e:
            logger.exception(f"❌ Error loading vector store: {e}")
            return None

    def query_documents(self, user_id: int, query: str, k: int = 4) -> List[dict]:
        """Query user's documents"""
        vectorstore = self.get_vectorstore(user_id)
        if vectorstore is None:
            logger.warning(f"📭 No vector store available for user {user_id}")
            return []

        try:
            logger.info(f"🔎 Querying: '{query}' (top {k} results)")
            results = vectorstore.similarity_search_with_score(query, k=k)
            
            formatted_results = [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": float(score)
                }
                for doc, score in results
            ]
            
            logger.info(f"✅ Found {len(formatted_results)} results")
            return formatted_results

        except Exception as e:
            logger.exception(f"❌ Error querying documents: {e}")
            return []