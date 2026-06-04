class LLMService:
    async def embed_text(self, text: str) -> list[float]:
            response = await self.client.embeddings.create(
                model=self.embedding_model,
                input=text,
            )
    
            return response.data[0].embedding