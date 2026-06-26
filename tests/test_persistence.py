import unittest
import uuid
from pathlib import Path
import shutil

from server import persistence
from server.state import WorkspaceState


class PersistenceTests(unittest.TestCase):
    def test_save_and_load_view_round_trip(self) -> None:
        root = Path(".test_tmp") / f"persistence-{uuid.uuid4().hex}"
        root.mkdir(parents=True, exist_ok=True)
        try:
            self._with_saved_view_dir(root.resolve(), self._round_trip_case)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_safe_filename_normalizes_display_name(self) -> None:
        self.assertEqual(persistence.safe_filename("  Alpha / Beta  "), "Alpha_Beta")
        self.assertEqual(persistence.safe_filename("..."), "view")

    def _round_trip_case(self, root: Path) -> None:
        state = WorkspaceState(name="Team Review", description="Showpiece pass")
        path = persistence.save_view(state)
        reloaded = persistence.load_view(path)

        self.assertEqual(reloaded.name, "Team Review")
        self.assertEqual(reloaded.description, "Showpiece pass")
        self.assertEqual(path.parent, root)

    def _with_saved_view_dir(self, root: Path, callback) -> None:
        original_dir = persistence.SAVED_VIEWS_DIR
        original_autosave = persistence.AUTOSAVE_PATH
        try:
            persistence.SAVED_VIEWS_DIR = root
            persistence.AUTOSAVE_PATH = root / "_autosave.json"
            callback(root)
        finally:
            persistence.SAVED_VIEWS_DIR = original_dir
            persistence.AUTOSAVE_PATH = original_autosave


if __name__ == "__main__":
    unittest.main()
