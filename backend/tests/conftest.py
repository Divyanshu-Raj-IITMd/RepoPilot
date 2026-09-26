"""Shared pytest fixtures: a RepoManager with the bundled demo repo."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import get_settings  # noqa: E402
from app.repo_manager import RepoManager  # noqa: E402


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture(scope="session")
def manager(settings):
    return RepoManager(settings)


@pytest.fixture(scope="session")
def demo_repo(manager):
    return manager.demo_repo()
