# app/rag/__init__.py
"""
RAG (Retrieval-Augmented Generation) module for CustomerSupportFlow.

Scrapes Walmart policy documents using Scrapling, chunks them,
and stores them in a local ChromaDB collection for fast semantic
retrieval by the Response+RAG agent.
"""
