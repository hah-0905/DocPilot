import asyncio

from sentence_transformers import CrossEncoder


class RerankService:

    def __init__(self)->None:
        # 延迟加载，避免后端启动时立即下载、加载模型
        self._model: CrossEncoder | None = None

        # 避免多个请求同时加载模型或同时执行预测
        self._predict_lock = asyncio.Lock()

    def _predict(self, pairs: list[list[str]]):
        if self._model is None:
            self._model = CrossEncoder(
                "BAAI/bge-reranker-v2-m3",
                max_length=512,
            )

        return self._model.predict(pairs)

    async def rerank(
            self,
            query: str,
            chunks: list[dict],
            top_k: int,
    ) -> list[dict]:
        """对向量召回的文本块进行重排序。"""
        if not chunks or top_k <= 0:
            return []

        pairs = [
            [query, chunk["content"]]
            for chunk in chunks
        ]

        async with self._predict_lock:
            scores = await asyncio.to_thread(
                self._predict,
                pairs
            )

        ranked_chunks: list[dict] = []

        for chunk, score in zip(chunks, scores):
            item = chunk.copy()

            # 保留原来的向量分数
            item["vector_score"] = item.get("score")

            # score 改成 rerank 分数
            item["rerank_score"] = float(score)
            item["score"] = float(score)

            ranked_chunks.append(item)

        ranked_chunks.sort(
            key=lambda x: x["rerank_score"],
            reverse=True
        )

        return ranked_chunks[:top_k]


# 每个后端进程共用一个重排服务，避免重复加载模型
rerank_service = RerankService()
