from typing import List, Dict, Any, Optional, Union
from rank_bm25 import BM25Okapi
import nltk
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import chromadb
from chromadb.config import Settings
import pickle
from nltk.tokenize import word_tokenize
import os
import json

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

def simple_tokenize(text):
    return word_tokenize(text)


class OpenAIEmbeddingModel:
    """Adapter that mimics SentenceTransformer for OpenAI embeddings."""

    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL, api_key: Optional[str] = None):
        from openai import OpenAI

        self.model_name = model_name
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if self.api_key is None:
            raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
        base_url = os.getenv("OPENAI_BASE_URL")
        client_kwargs = {"api_key": self.api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = OpenAI(**client_kwargs)

    def encode(self, texts):
        if isinstance(texts, str):
            texts = [texts]

        embeddings = []
        for start in range(0, len(texts), 100):
            batch = texts[start:start + 100]
            response = self.client.embeddings.create(model=self.model_name, input=batch)
            embeddings.extend(item.embedding for item in response.data)

        return np.array(embeddings, dtype=np.float32)

    def get_config_dict(self):
        return {"model_name": self.model_name, "backend": "openai"}


class OpenAIChromaEmbeddingFunction:
    """Embedding function for ChromaDB backed by OpenAI embeddings."""

    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL, api_key: Optional[str] = None):
        self.model_name = model_name
        self.model = OpenAIEmbeddingModel(model_name=model_name, api_key=api_key)

    def __call__(self, input: List[str]) -> List[List[float]]:
        return self.model.encode(input).tolist()


def build_embedding_model(model_name: str = DEFAULT_EMBEDDING_MODEL):
    requested_model = model_name or DEFAULT_EMBEDDING_MODEL

    if requested_model.startswith("text-embedding-"):
        return OpenAIEmbeddingModel(requested_model)

    if SentenceTransformer is not None:
        try:
            return SentenceTransformer(requested_model)
        except Exception:
            pass

    fallback_model = os.getenv("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    return OpenAIEmbeddingModel(fallback_model)


def build_chroma_embedding_function(model_name: str = DEFAULT_EMBEDDING_MODEL):
    requested_model = model_name or DEFAULT_EMBEDDING_MODEL

    if requested_model.startswith("text-embedding-"):
        return OpenAIChromaEmbeddingFunction(requested_model)

    try:
        return SentenceTransformerEmbeddingFunction(model_name=requested_model)
    except Exception:
        fallback_model = os.getenv("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
        return OpenAIChromaEmbeddingFunction(fallback_model)

class ChromaRetriever:
    """Vector database retrieval using ChromaDB"""
    def __init__(self, collection_name: str = "memories",model_name: str = DEFAULT_EMBEDDING_MODEL):
        """Initialize ChromaDB retriever.
        
        Args:
            collection_name: Name of the ChromaDB collection
        """
        self.client = chromadb.Client(Settings(allow_reset=True))
        self.embedding_function = build_chroma_embedding_function(model_name=model_name)
        self.collection = self.client.get_or_create_collection(name=collection_name,embedding_function=self.embedding_function)
        
    def add_document(self, document: str, metadata: Dict, doc_id: str):
        """Add a document to ChromaDB with enhanced embedding using metadata.
        
        Args:
            document: Text content to add
            metadata: Dictionary of metadata including keywords, tags, context
            doc_id: Unique identifier for the document
        """
        # Build enhanced document content including semantic metadata
        enhanced_document = document
        
        # Add context information
        if 'context' in metadata and metadata['context'] != "General":
            enhanced_document += f" context: {metadata['context']}"
        
        # Add keywords information    
        if 'keywords' in metadata and metadata['keywords']:
            keywords = metadata['keywords'] if isinstance(metadata['keywords'], list) else json.loads(metadata['keywords'])
            if keywords:
                enhanced_document += f" keywords: {', '.join(keywords)}"
        
        # Add tags information
        if 'tags' in metadata and metadata['tags']:
            tags = metadata['tags'] if isinstance(metadata['tags'], list) else json.loads(metadata['tags'])
            if tags:
                enhanced_document += f" tags: {', '.join(tags)}"
        
        # Convert MemoryNote object to serializable format
        processed_metadata = {}
        for key, value in metadata.items():
            if isinstance(value, list):
                processed_metadata[key] = json.dumps(value)
            elif isinstance(value, dict):
                processed_metadata[key] = json.dumps(value)
            else:
                processed_metadata[key] = str(value)
        
        # Store enhanced document content for better embedding
        processed_metadata['enhanced_content'] = enhanced_document
                
        # Use enhanced document content for embedding generation
        self.collection.add(
            documents=[enhanced_document],
            metadatas=[processed_metadata],
            ids=[doc_id]
        )
        
    def delete_document(self, doc_id: str):
        """Delete a document from ChromaDB.
        
        Args:
            doc_id: ID of document to delete
        """
        self.collection.delete(ids=[doc_id])
        
    def search(self, query: str, k: int = 5):
        """Search for similar documents.
        
        Args:
            query: Query text
            k: Number of results to return
            
        Returns:
            Dict with documents, metadatas, ids, and distances
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=k
        )
        
        # Convert string metadata back to original types
        if 'metadatas' in results and results['metadatas'] and len(results['metadatas']) > 0:
            # First level is a list with one item per query
            for i in range(len(results['metadatas'])):
                # Second level is a list of metadata dicts for each result
                if isinstance(results['metadatas'][i], list):
                    for j in range(len(results['metadatas'][i])):
                        # Process each metadata dict
                        if isinstance(results['metadatas'][i][j], dict):
                            metadata = results['metadatas'][i][j]
                            for key, value in metadata.items():
                                try:
                                    # Try to parse JSON for lists and dicts
                                    if isinstance(value, str) and (value.startswith('[') or value.startswith('{')):
                                        metadata[key] = json.loads(value)
                                    # Convert numeric strings back to numbers
                                    elif isinstance(value, str) and value.replace('.', '', 1).isdigit():
                                        if '.' in value:
                                            metadata[key] = float(value)
                                        else:
                                            metadata[key] = int(value)
                                except (json.JSONDecodeError, ValueError):
                                    # If parsing fails, keep the original string
                                    pass
                        
        return results
