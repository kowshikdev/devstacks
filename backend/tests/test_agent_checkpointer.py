import asyncio
import os

import pytest

from devstacks_agent.checkpointer import CheckpointerUnavailableError, get_checkpointer, thread_id_for


def test_thread_id_is_stable_per_ingestion_event():
    thread_id = thread_id_for("profile-1", "artifact-1", "version-1")

    assert thread_id == "claim-extraction:profile-1:artifact-1:version-1"
    assert thread_id_for("profile-1", "artifact-1", "version-1") == thread_id


def test_get_checkpointer_requires_supabase_db_url():
    original = os.environ.pop("SUPABASE_DB_URL", None)
    try:
        async def attempt():
            async with get_checkpointer():
                pass

        with pytest.raises(CheckpointerUnavailableError):
            asyncio.run(attempt())
    finally:
        if original is not None:
            os.environ["SUPABASE_DB_URL"] = original
