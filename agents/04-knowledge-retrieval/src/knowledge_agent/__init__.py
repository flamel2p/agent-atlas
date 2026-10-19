"""Extractive knowledge agent: retrieve evidence, select IDs, validate source quotes.

Start at ``engine.run`` for control flow. ``corpus`` owns source validation and
scope, ``retrieval`` owns ranking/citations, and ``provider`` only selects evidence.
"""
