from datetime import UTC, datetime

import pytest

from memory_agent.agent import ask
from memory_agent.contracts import Request


@pytest.fixture
def now():
    return datetime(2026, 10, 19, 1, 0, tzinfo=UTC)


@pytest.fixture
def turn(tmp_path, now):
    def run(*, user="learner-a", session="session-one", query="What is working memory?", remember_style=None,
            mode="replay", store="demo", at=None, selector=None):
        return ask(Request(user, session, query, remember_style, mode, store), case_root=tmp_path,
                   now=at or now, selector=selector)
    return run
