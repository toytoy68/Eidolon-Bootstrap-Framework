# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : sqlite_errors.py
# Description : Distinction des verrous SQLite réels et des erreurs de stockage
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Classify only SQLite's numeric BUSY/LOCKED codes, never exception text.

Extended result codes retain the primary code in their low byte. A query budget
interruption, damaged database or missing file is not a transient lock. This
helper does not retry anything and says nothing about whether a write committed.
"""
import sqlite3


def is_busy(exc):
    code = getattr(exc, "sqlite_errorcode", None)
    return (isinstance(exc, sqlite3.Error) and type(code) is int
            and (code & 0xff) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED))
