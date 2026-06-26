import tempfile
import unittest
from importlib.util import find_spec
from pathlib import Path


if find_spec("chromadb"):
    from server.services.path_service import resolve_chroma_path
else:
    resolve_chroma_path = None


@unittest.skipUnless(resolve_chroma_path is not None, "chromadb is not installed in this environment")
class ResolveChromaPathTests(unittest.TestCase):
    def test_accepts_directory_with_sqlite_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "chroma.sqlite3").write_text("", encoding="utf-8")

            path, validation = resolve_chroma_path(root)

            self.assertEqual(path, root.resolve())
            self.assertTrue(validation["valid"])

    def test_promotes_sqlite_file_to_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sqlite_path = root / "chroma.sqlite3"
            sqlite_path.write_text("", encoding="utf-8")

            path, validation = resolve_chroma_path(sqlite_path)

            self.assertEqual(path, root.resolve())
            self.assertTrue(validation["valid"])
            self.assertIn("SQLite file", validation["message"])


if __name__ == "__main__":
    unittest.main()
