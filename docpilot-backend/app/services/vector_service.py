from dataclasses import dataclass
from pathlib import Path

import chromadb


@dataclass
class VectorHit:
    vector_id: str
    score: float


class VectorService:
    vector_store_type = "chroma"
    vector_collection = "docpilot_chunks"

    def __init__(self) -> None:
        persist_dir = Path(__file__).resolve().parents[2] / "chroma_db"
        self.client = chromadb.PersistentClient(path=str(persist_dir))
        self.collection = self.client.get_or_create_collection(
            name=self.vector_collection,
            metadata={"hnsw:space": "cosine"},
        )

    async def upsert_chunk_vector(
        self,
        vector_id: str,
        embedding: list[float],
        metadata: dict,
    ) -> None:
        """
        在向量数据库中插入或更新一个文本块的向量表示。
        
        该方法将给定的向量 ID、嵌入向量和元数据作为一条记录插入到集合中；
        如果指定 ID 已存在，则会覆盖原有记录（即执行“upsert”操作）。

        参数:
            vector_id (str): 向量的唯一标识符，用于在集合中定位该向量。
            embedding (list[float]): 文本块对应的嵌入向量，通常由嵌入模型生成。
            metadata (dict): 与该向量关联的附加信息，如来源文档、时间戳等。

        返回值:
            None
        """
        self.collection.upsert(
            ids=[vector_id],
            embeddings=[embedding],
            metadatas=[metadata],
        )

    async def search_similar_chunks(
        self,
        embedding: list[float],
        kb_id: int,
        top_k: int,
    ) -> list[VectorHit]:
        """
        在向量数据库中搜索与给定嵌入向量最相似的文本块。

        该方法使用指定的知识库 ID（kb_id）作为过滤条件，从向量集合中检索与输入嵌入最接近的 top_k 个结果，
        并将原始距离转换为相似度得分（score = 1.0 - distance）。

        参数:
            embedding (list[float]): 查询用的嵌入向量，用于计算与数据库中向量的相似度。
            kb_id (int): 知识库的唯一标识符，用于限定搜索范围。
            top_k (int): 返回的最相似结果数量。

        返回:
            list[VectorHit]: 包含匹配向量 ID 和相似度得分的 VectorHit 对象列表，按相似度降序排列。
        """
        result = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where={"kb_id": kb_id},
        )
        ids = result.get("ids", [[]])[0]
        distances = result.get("distances", [[]])[0]

        hits: list[VectorHit] = []
        for vector_id, distance in zip(ids, distances):
            hits.append(
                VectorHit(
                    vector_id=vector_id,
                    score=1.0 - float(distance),
                )
            )
        return hits

    async def delete_vectors(self, vector_ids: list[str]) -> None:
        """
        从向量集合中删除指定ID的向量。

        参数:
            vector_ids (list[str]): 要删除的向量ID列表。若为空列表，则不执行任何操作。

        返回值:
            None
        """
        if not vector_ids:
            return
        self.collection.delete(ids=vector_ids)