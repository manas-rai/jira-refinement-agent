"""
Context retriever — stub for fetching similar historical tickets.

Replace this with a real RAG implementation (e.g. Pinecone, pgvector, Chroma)
when you're ready to add historical context.
"""

from structlog import get_logger

logger = get_logger()


async def get_similar_tickets(
    summary: str,
    description: str,
) -> list[dict]:
    """Retrieve similar past tickets for context.

    **This is a stub.** It returns an empty list. To enable RAG:
    1. Index your past Jira tickets / Confluence pages into a vector store.
    2. Embed the current ticket's summary + description.
    3. Query the vector store for top-K similar documents.
    4. Return them as a list of dicts with 'summary' and 'description' keys.

    Args:
        summary: Current ticket summary.
        description: Current ticket description text.

    Returns:
        List of similar ticket dicts (empty for now).
    """
    logger.debug(
        "similar_tickets_stub",
        summary_len=len(summary),
        description_len=len(description),
    )
    return []
