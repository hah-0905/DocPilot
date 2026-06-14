from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk_embeddings import ChunkEmbedding
from app.models.documents import DocumentChunk
from app.services.llm_service import LLMService
from app.services.vector_service import VectorService


class RagService:
    def __init__(self) -> None:
        self.llm_service = LLMService()
        self.vector_service = VectorService()

    async def search(
        self,
        db: AsyncSession,
        kb_id: int,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        '''
        Search for similar chunks in the vector store.
        '''
        query_embedding = await self.llm_service.embed_text(query)
        hits = await self.vector_service.search_similar_chunks(
            embedding=query_embedding,
            kb_id=kb_id,
            top_k=top_k,
        )
        if not hits:
            return []

        vector_ids = [hit.vector_id for hit in hits]
        score_by_vector_id = {hit.vector_id: hit.score for hit in hits}

        result = await db.execute(
            select(DocumentChunk, ChunkEmbedding)
            .join(
                ChunkEmbedding,
                ChunkEmbedding.chunk_id == DocumentChunk.id,
            )
            .where(
                DocumentChunk.kb_id == kb_id,
                ChunkEmbedding.kb_id == kb_id,
                ChunkEmbedding.vector_store_type == self.vector_service.vector_store_type,
                ChunkEmbedding.vector_collection == self.vector_service.vector_collection,
                ChunkEmbedding.embedding_model == self.llm_service.embedding_model,
                ChunkEmbedding.status == "active",
                ChunkEmbedding.vector_id.in_(vector_ids),
            )
        )

        chunk_by_vector_id = {
            embedding.vector_id: chunk
            for chunk, embedding in result.all()
        }

        references: list[dict] = []
        for vector_id in vector_ids:
            chunk = chunk_by_vector_id.get(vector_id)
            if not chunk:
                continue

            references.append(
                {
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "content": chunk.content,
                    "score": score_by_vector_id[vector_id],
                }
            )

        return references

    async def rag_chat(
        self,
        db: AsyncSession,
        kb_id: int,
        question: str,
        top_k: int = 5,
    ) -> dict:
        '''
        RAG 聊天
        '''
        retrieved_chunks = await self.search(
            db,
            kb_id=kb_id,
            query=question,
            top_k=top_k,
        )

        context = "\n\n".join(
            f"[Chunk {index + 1}]\n{chunk['content']}"
            for index, chunk in enumerate(retrieved_chunks)
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a careful knowledge-base Q&A assistant. "
                    "Answer primarily from the provided context. "
                    "If the context does not contain the answer, say that the "
                    "knowledge base does not include the relevant information."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Context:\n{context}\n\n"
                    f"Question:\n{question}\n\n"
                    "Please answer based on the context."
                ),
            },
        ]
        answer = await self.llm_service.chat(messages)

        return {
            "answer": answer,
            "references": retrieved_chunks,
        }
