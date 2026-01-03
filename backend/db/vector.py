"""ChromaDB vector store for semantic search over transactions."""

import chromadb
from chromadb.config import Settings as ChromaSettings
from litellm import aembedding

from backend.config import settings
from backend.models import Transaction


class VectorStore:
    """ChromaDB-based vector store for transaction embeddings."""

    def __init__(self):
        settings.ensure_directories()

        # Initialize ChromaDB with persistent storage
        self._client = chromadb.PersistentClient(
            path=str(settings.chroma_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        # Get or create the transactions collection
        self._collection = self._client.get_or_create_collection(
            name="transactions",
            metadata={"description": "Financial transaction embeddings"},
        )

    async def add_transaction(self, transaction: Transaction) -> None:
        """Add a transaction to the vector store."""
        # Create embedding text from transaction details
        embed_text = self._create_embed_text(transaction)

        # Generate embedding
        embedding = await self._get_embedding(embed_text)

        if embedding:
            self._collection.upsert(
                ids=[str(transaction.id)],
                embeddings=[embedding],
                documents=[embed_text],
                metadatas=[
                    {
                        "date": transaction.date.isoformat(),
                        "amount": transaction.amount,
                        "category": transaction.category.value if transaction.category else "Unknown",
                        "source": transaction.source.value,
                        "description": transaction.description,
                        "tags": ",".join(transaction.tags) if transaction.tags else "",
                    }
                ],
            )

    async def add_transactions_batch(self, transactions: list[Transaction]) -> None:
        """Add multiple transactions to the vector store."""
        if not transactions:
            return

        # Create embedding texts
        embed_texts = [self._create_embed_text(txn) for txn in transactions]

        # Generate embeddings in batch
        embeddings = await self._get_embeddings_batch(embed_texts)

        if embeddings and len(embeddings) == len(transactions):
            self._collection.upsert(
                ids=[str(txn.id) for txn in transactions],
                embeddings=embeddings,
                documents=embed_texts,
                metadatas=[
                    {
                        "date": txn.date.isoformat(),
                        "amount": txn.amount,
                        "category": txn.category.value if txn.category else "Unknown",
                        "source": txn.source.value,
                        "description": txn.description,
                        "tags": ",".join(txn.tags) if txn.tags else "",
                    }
                    for txn in transactions
                ],
            )

    async def search(
        self,
        query: str,
        n_results: int = 20,
        category_filter: str | None = None,
    ) -> list[dict]:
        """
        Search for transactions semantically similar to the query.

        Returns a list of results with transaction IDs and metadata.
        """
        # Generate query embedding
        query_embedding = await self._get_embedding(query)

        if not query_embedding:
            return []

        # Build where filter if category specified
        where_filter = None
        if category_filter:
            where_filter = {"category": category_filter}

        # Search
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        # Format results
        formatted = []
        if results["ids"] and results["ids"][0]:
            for i, txn_id in enumerate(results["ids"][0]):
                formatted.append(
                    {
                        "id": txn_id,
                        "document": results["documents"][0][i] if results["documents"] else None,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else None,
                        "distance": results["distances"][0][i] if results["distances"] else None,
                    }
                )

        return formatted

    def get_collection_count(self) -> int:
        """Get the number of items in the collection."""
        return self._collection.count()

    def _create_embed_text(self, transaction: Transaction) -> str:
        """Create text to embed for a transaction."""
        category_str = transaction.category.value if transaction.category else "Unknown"
        tags_str = ", ".join(transaction.tags) if transaction.tags else ""
        base = f"{transaction.description} | Category: {category_str} | Amount: ${abs(transaction.amount):.2f}"
        if tags_str:
            base += f" | Tags: {tags_str}"
        return base

    async def _get_embedding(self, text: str) -> list[float] | None:
        """Get embedding for a single text."""
        try:
            if settings.llm_provider == "openai":
                response = await aembedding(
                    model="text-embedding-3-small",
                    input=[text],
                    api_key=settings.openai_api_key,
                )
            else:
                response = await aembedding(
                    model=f"ollama/{settings.embedding_model}",
                    input=[text],
                    api_base=settings.ollama_host,
                )

            return response.data[0]["embedding"]
        except Exception as e:
            print(f"Embedding error: {e}")
            return None

    async def _get_embeddings_batch(self, texts: list[str]) -> list[list[float]] | None:
        """Get embeddings for multiple texts."""
        try:
            if settings.llm_provider == "openai":
                response = await aembedding(
                    model="text-embedding-3-small",
                    input=texts,
                    api_key=settings.openai_api_key,
                )
            else:
                response = await aembedding(
                    model=f"ollama/{settings.embedding_model}",
                    input=texts,
                    api_base=settings.ollama_host,
                )

            return [item["embedding"] for item in response.data]
        except Exception as e:
            print(f"Batch embedding error: {e}")
            return None


# Global vector store instance
vector_store = VectorStore()
