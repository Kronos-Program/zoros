"""LangChain Integration Plugin for ZorOS

Provides LangChain integration for orchestration, document processing,
and advanced LLM workflows.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import logging

from source.plugins.base import (
    ZorosPlugin, 
    LanguageBackendPlugin, 
    DocumentProcessorPlugin
)

logger = logging.getLogger(__name__)


class LangChainPlugin(ZorosPlugin):
    """LangChain integration plugin for ZorOS."""
    
    @property
    def name(self) -> str:
        return "LangChain Integration"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "LangChain integration for advanced LLM orchestration and document processing"
    
    @property
    def dependencies(self) -> List[str]:
        return [
            "langchain",
            "langchain-community", 
            "langchain-core",
            "langchain-openai"
        ]
    
    @property
    def optional_dependencies(self) -> List[str]:
        return [
            "unstructured",
            "chromadb",
            "faiss-cpu",
            "pypdf",
            "python-docx"
        ]
    
    def initialize(self, plugin_manager: Any) -> None:
        """Initialize the LangChain plugin."""
        logger.info(f"Initializing {self.name}")
        
        # Check if dependencies are available
        self._check_dependencies()
        
        # Register LangChain backends
        plugin_manager.register_language_backend("langchain_openai", LangChainOpenAIBackend)
        plugin_manager.register_document_processor("langchain_processor", LangChainDocumentProcessor)
        plugin_manager.register_orchestrator("langchain_chain", LangChainOrchestrator)
        
        logger.info("LangChain plugin initialized successfully")
    
    def _check_dependencies(self) -> None:
        """Check if required dependencies are available."""
        try:
            import langchain
            import langchain_core
            logger.info(f"LangChain version {langchain.__version__} available")
        except ImportError:
            logger.warning("LangChain not available - install with: pip install langchain")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the LangChain plugin."""
        status = {
            "name": self.name,
            "version": self.version,
            "status": "healthy",
            "details": {
                "langchain_available": False,
                "backends_registered": 0,
                "processors_registered": 0
            }
        }
        
        try:
            import langchain
            status["details"]["langchain_available"] = True
            status["details"]["langchain_version"] = langchain.__version__
        except ImportError:
            status["status"] = "degraded"
            status["details"]["error"] = "LangChain not installed"
        
        return status


class LangChainOpenAIBackend:
    """LangChain OpenAI backend for language processing."""
    
    def __init__(self):
        self.name = "langchain_openai"
        self.description = "LangChain OpenAI integration"
        self._llm = None
    
    def _get_llm(self):
        """Get or create LangChain LLM instance."""
        if self._llm is None:
            try:
                from langchain_openai import ChatOpenAI
                self._llm = ChatOpenAI(
                    model="gpt-3.5-turbo",
                    temperature=0.7
                )
            except ImportError:
                logger.error("LangChain OpenAI not available")
                return None
        return self._llm
    
    def complete_turn(self, prompt: str, context: Dict[str, Any]) -> str:
        """Complete a turn using LangChain."""
        llm = self._get_llm()
        if llm is None:
            return "LangChain OpenAI backend not available"
        
        try:
            from langchain_core.messages import HumanMessage
            messages = [HumanMessage(content=prompt)]
            response = llm.invoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"LangChain completion error: {e}")
            return f"Error: {e}"
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get available OpenAI models via LangChain."""
        return [
            {
                "name": "gpt-3.5-turbo",
                "description": "OpenAI GPT-3.5 Turbo via LangChain",
                "context_length": 4096,
                "capabilities": ["chat", "completion"]
            },
            {
                "name": "gpt-4",
                "description": "OpenAI GPT-4 via LangChain", 
                "context_length": 8192,
                "capabilities": ["chat", "completion", "reasoning"]
            }
        ]


class LangChainDocumentProcessor:
    """LangChain-based document processor."""
    
    def __init__(self):
        self.name = "langchain_processor"
        self.description = "Document processing using LangChain loaders"
    
    def process_document(self, doc_path: Path, options: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process document using LangChain loaders."""
        try:
            # Determine document type and use appropriate loader
            if doc_path.suffix.lower() == '.pdf':
                return self._process_pdf(doc_path, options)
            elif doc_path.suffix.lower() in ['.txt', '.md']:
                return self._process_text(doc_path, options)
            elif doc_path.suffix.lower() in ['.docx', '.doc']:
                return self._process_word(doc_path, options)
            else:
                logger.warning(f"Unsupported document type: {doc_path.suffix}")
                return []
        
        except Exception as e:
            logger.error(f"Document processing error: {e}")
            return []
    
    def _process_pdf(self, doc_path: Path, options: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process PDF using LangChain PDF loader."""
        try:
            from langchain_community.document_loaders import PyPDFLoader
            
            loader = PyPDFLoader(str(doc_path))
            documents = loader.load()
            
            return [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "type": "pdf_page",
                    "source": str(doc_path)
                }
                for doc in documents
            ]
        
        except ImportError:
            logger.error("PyPDF loader not available - install with: pip install pypdf")
            return []
    
    def _process_text(self, doc_path: Path, options: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process text file using LangChain text loader."""
        try:
            from langchain_community.document_loaders import TextLoader
            
            loader = TextLoader(str(doc_path))
            documents = loader.load()
            
            return [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "type": "text",
                    "source": str(doc_path)
                }
                for doc in documents
            ]
        
        except Exception as e:
            logger.error(f"Text processing error: {e}")
            return []
    
    def _process_word(self, doc_path: Path, options: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process Word document using LangChain."""
        try:
            from langchain_community.document_loaders import Docx2txtLoader
            
            loader = Docx2txtLoader(str(doc_path))
            documents = loader.load()
            
            return [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "type": "docx",
                    "source": str(doc_path)
                }
                for doc in documents
            ]
        
        except ImportError:
            logger.error("Docx loader not available - install with: pip install python-docx")
            return []
    
    def get_supported_formats(self) -> List[str]:
        """Get supported document formats."""
        return ['pdf', 'txt', 'md', 'docx', 'doc']


class LangChainOrchestrator:
    """LangChain-based workflow orchestrator."""
    
    def __init__(self):
        self.name = "langchain_chain"
        self.description = "LangChain chain orchestration"
    
    def create_rag_chain(self, documents: List[Dict[str, Any]], query: str) -> str:
        """Create a RAG (Retrieval Augmented Generation) chain."""
        try:
            from langchain_core.documents import Document
            from langchain_openai import ChatOpenAI, OpenAIEmbeddings
            from langchain_community.vectorstores import FAISS
            from langchain.chains import RetrievalQA
            
            # Convert documents to LangChain Document format
            docs = [
                Document(page_content=doc["content"], metadata=doc.get("metadata", {}))
                for doc in documents
            ]
            
            # Create vector store
            embeddings = OpenAIEmbeddings()
            vector_store = FAISS.from_documents(docs, embeddings)
            
            # Create retrieval chain
            llm = ChatOpenAI(model="gpt-3.5-turbo")
            qa_chain = RetrievalQA.from_chain_type(
                llm=llm,
                chain_type="stuff",
                retriever=vector_store.as_retriever()
            )
            
            # Run query
            result = qa_chain.invoke({"query": query})
            return result["result"]
        
        except ImportError as e:
            logger.error(f"RAG chain dependencies not available: {e}")
            return f"Error: Missing dependencies for RAG chain"
        except Exception as e:
            logger.error(f"RAG chain error: {e}")
            return f"Error: {e}"
    
    def create_summarization_chain(self, text: str) -> str:
        """Create a text summarization chain."""
        try:
            from langchain.chains.summarize import load_summarize_chain
            from langchain_openai import ChatOpenAI
            from langchain_core.documents import Document
            
            llm = ChatOpenAI(model="gpt-3.5-turbo")
            docs = [Document(page_content=text)]
            
            chain = load_summarize_chain(llm, chain_type="stuff")
            result = chain.invoke(docs)
            
            return result["output_text"]
        
        except Exception as e:
            logger.error(f"Summarization chain error: {e}")
            return f"Error: {e}"