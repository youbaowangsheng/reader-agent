import re
import json
import math
import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from sqlalchemy import select, text, delete
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI

from app.model.paper_chunk import PaperChunk
from app.model.paper_chunk_vector import PaperChunkVector
from config import get_settings

settings = get_settings()

# OpenAI client for embeddings
_openai_client: Optional[AsyncOpenAI] = None


def get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
    return _openai_client


def chunk_text(text: str, max_chars: int = 900, overlap_chars: int = 150) -> List[str]:
    """Split text into overlapping chunks."""
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    start = 0
    step = max(1, max_chars - overlap_chars)
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start += step
    return [c for c in chunks if c]


@dataclass
class RetrievedChunk:
    chunk_id: str
    score: float
    heading: str
    page_range: str
    chapter_index: Optional[int]
    text: str


class RAGService:
    """RAG service with pgvector for vector storage and retrieval."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def build_index(self, paper_id: str, parsed_doc: Dict[str, Any]) -> int:
        """Chunk document, generate embeddings, store in pgvector. Returns chunk count."""
        # 清理旧 chunks + vectors（幂等重建，避免重复解析时的唯一约束冲突）
        await self.db.execute(delete(PaperChunkVector).where(PaperChunkVector.paper_id == paper_id))
        await self.db.execute(delete(PaperChunk).where(PaperChunk.paper_id == paper_id))
        await self.db.commit()

        chunk_count = 0

        for sec in parsed_doc.get("sections", []):
            heading = sec.get("heading", "Section")
            page_range = str(sec.get("page_range", ""))
            chapter_index = sec.get("chapter_index")

            for part in chunk_text(sec.get("content", "")):
                chunk_count += 1
                chunk_id = f"doc_{paper_id[:8]}_c{chunk_count:04d}"

                # Store chunk
                chunk = PaperChunk(
                    paper_id=paper_id,
                    chunk_id=chunk_id,
                    heading=heading,
                    page_range=page_range,
                    chapter_index=chapter_index,
                    content=part,
                )
                self.db.add(chunk)

                # Generate and store embedding
                embedding = await self._generate_embedding(part)
                vector = PaperChunkVector(
                    paper_id=paper_id,
                    chunk_id=chunk_id,
                    embedding=json.dumps(embedding),
                )
                self.db.add(vector)

        await self.db.commit()
        return chunk_count

    async def search(
        self,
        paper_id: str,
        query: str,
        top_k: int = 5,
    ) -> List[RetrievedChunk]:
        """Search chunks by cosine similarity using pgvector."""
        query_embedding = await self._generate_embedding(query)

        # Use raw SQL for pgvector cosine similarity search
        # pgvector <=> operator is cosine distance, so 1 - distance = similarity
        embedding_json = json.dumps(query_embedding)

        # Use CAST for type conversion to avoid :: parsing issues with named params
        query_text = """
            SELECT
                pc.chunk_id,
                pc.heading,
                pc.page_range,
                pc.chapter_index,
                pc.content,
                1 - (CAST(pcv.embedding AS vector) <=> CAST(:embedding AS vector)) AS score
            FROM paper_chunks_vectors pcv
            JOIN paper_chunks pc ON pc.chunk_id = pcv.chunk_id AND pc.paper_id = pcv.paper_id
            WHERE pcv.paper_id = :paper_id
            ORDER BY CAST(pcv.embedding AS vector) <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """

        sql = text(query_text)
        result = await self.db.execute(
            sql,
            {"embedding": embedding_json, "paper_id": paper_id, "top_k": top_k},
        )
        rows = result.fetchall()

        return [
            RetrievedChunk(
                chunk_id=row.chunk_id,
                score=float(row.score),
                heading=row.heading,
                page_range=row.page_range,
                chapter_index=row.chapter_index,
                text=row.content,
            )
            for row in rows
        ]

    async def get_chunk(self, paper_id: str, chunk_id: str) -> Optional[PaperChunk]:
        """Get a specific chunk by ID."""
        stmt = select(PaperChunk).where(
            PaperChunk.paper_id == paper_id,
            PaperChunk.chunk_id == chunk_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using OpenAI API."""
        if not settings.openai_api_key:
            # Fallback to hash-based only if no API key configured (not recommended)
            return self._hash_embedding(text)

        try:
            client = get_openai_client()
            response = await client.embeddings.create(
                model=settings.openai_model,
                input=text[:8192],  # OpenAI has 8192 token limit
            )
            return response.data[0].embedding
        except Exception as e:
            # embedding API 失败（如模型不支持/404）→ 回退 hash，不阻塞解析
            print(f"Embedding API failed, fallback to hash: {str(e)[:120]}")
            return self._hash_embedding(text)

    @staticmethod
    def _hash_embedding(text: str, dim: int = 1536) -> List[float]:
        """Fallback deterministic hash embedding (not recommended for production)."""
        vec = [0.0] * dim
        tokens = re.findall(r"[A-Za-z0-9_]+|[一-鿿]", text.lower())
        if not tokens:
            return vec

        for tok in tokens:
            h = hashlib.md5(tok.encode("utf-8")).digest()
            idx = int.from_bytes(h[:4], "big") % dim
            sign = 1.0 if (h[4] % 2 == 0) else -1.0
            vec[idx] += sign

        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec