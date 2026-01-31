"""LangSmith tracing setup and utilities."""

import os
from contextlib import contextmanager
from typing import Any, Generator

from langsmith import Client
from langsmith.run_helpers import traceable

from rtc.config import get_settings


def setup_tracing() -> Client | None:
    """Initialize LangSmith tracing.

    Returns:
        LangSmith client if configured, None otherwise.
    """
    settings = get_settings()

    if not settings.langsmith_api_key:
        return None

    # Set environment variables for LangSmith
    os.environ["LANGCHAIN_TRACING_V2"] = "true" if settings.langsmith_tracing else "false"
    os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project

    return Client(api_key=settings.langsmith_api_key)


def get_tracer() -> Client | None:
    """Get the LangSmith client.

    Returns:
        LangSmith client if API key is configured.
    """
    settings = get_settings()
    if settings.langsmith_api_key:
        return Client(api_key=settings.langsmith_api_key)
    return None


@contextmanager
def trace_node(
    name: str,
    run_type: str = "chain",
    metadata: dict[str, Any] | None = None,
) -> Generator[dict[str, Any], None, None]:
    """Context manager for tracing a pipeline node.

    Args:
        name: Name of the node
        run_type: Type of run (chain, llm, tool, etc.)
        metadata: Additional metadata to attach

    Yields:
        Dict for collecting outputs to be logged
    """
    outputs: dict[str, Any] = {}

    # The actual tracing is handled by LangGraph's built-in integration
    # This is a placeholder for additional custom tracing logic
    try:
        yield outputs
    finally:
        pass


def create_evaluation_dataset(
    client: Client,
    dataset_name: str,
    examples: list[dict[str, Any]],
) -> str:
    """Create a LangSmith evaluation dataset.

    Args:
        client: LangSmith client
        dataset_name: Name for the dataset
        examples: List of example dicts with 'inputs' and 'outputs' keys

    Returns:
        Dataset ID
    """
    dataset = client.create_dataset(dataset_name=dataset_name)

    for example in examples:
        client.create_example(
            inputs=example.get("inputs", {}),
            outputs=example.get("outputs", {}),
            dataset_id=dataset.id,
        )

    return str(dataset.id)
