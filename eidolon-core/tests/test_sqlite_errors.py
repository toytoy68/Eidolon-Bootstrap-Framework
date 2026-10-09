# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_sqlite_errors.py
# Description : Codes SQLite : verrou réel, code étendu, corruption et interruption
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import sqlite3
import unittest

from eidolon_core.sqlite_errors import is_busy


class SQLiteErrorTests(unittest.TestCase):
    def test_only_numeric_busy_and_locked_codes_are_classified(self):
        for code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED, sqlite3.SQLITE_BUSY | (2 << 8)):
            with self.subTest(code=code):
                error = sqlite3.OperationalError("private diagnostic must not be parsed")
                error.sqlite_errorcode = code
                self.assertTrue(is_busy(error))
        for code in (sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB, sqlite3.SQLITE_CANTOPEN,
                     sqlite3.SQLITE_INTERRUPT, sqlite3.SQLITE_IOERR, True, "5", None):
            with self.subTest(code=code):
                error = sqlite3.OperationalError("database is locked")
                error.sqlite_errorcode = code
                self.assertFalse(is_busy(error))
        self.assertFalse(is_busy(sqlite3.OperationalError("database is locked")))
        self.assertFalse(is_busy(ValueError("database is locked")))


if __name__ == "__main__":
    unittest.main()
