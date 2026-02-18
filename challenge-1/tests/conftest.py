"""Shared pytest fixtures for testing."""

import os
import sys

import pytest

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def sample_claim():
    """A simple static claim for testing."""
    return "The EU AI Act classifies AI applications into risk categories."


@pytest.fixture
def sample_dynamic_claim():
    """A dynamic claim for testing."""
    return "It is currently raining in Mumbai."


@pytest.fixture
def sample_invalid_claim():
    """An opinion/invalid claim for testing."""
    return "Python is the best programming language."


@pytest.fixture
def sample_evidence():
    """Sample evidence items for testing verification."""
    return [
        {
            "content": "The EU AI Act assigns applications of AI to three risk categories: "
                       "unacceptable risk, high-risk, and largely unregulated.",
            "source_url": "https://artificialintelligenceact.eu/",
            "source_title": "EU AI Act Overview",
        },
        {
            "content": "Applications that create an unacceptable risk, such as government-run "
                       "social scoring, are banned under the EU AI Act.",
            "source_url": "https://artificialintelligenceact.eu/high-level-summary/",
            "source_title": "EU AI Act Summary",
        },
    ]


@pytest.fixture
def sample_embedding():
    """A dummy embedding vector for testing."""
    return [0.01] * 1536
