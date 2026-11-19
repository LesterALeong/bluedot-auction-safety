import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import research_toolkit


ROOT = Path(__file__).resolve().parent


class ResearchToolkitTests(unittest.TestCase):
    def _copy_checkout(self, root):
        for path in (*ROOT.glob("*.py"), *ROOT.glob("*PROTOCOL.md")):
            shutil.copyfile(path, root / path.name)
        shutil.copytree(ROOT / "results", root / "results")

    def _assert_audit_failure(self, root, message):
        result = subprocess.run(
            [sys.executable, "-S", "-B", str(root / "research_toolkit.py"), "check-in"],
            cwd=root.parent,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn(message, result.stderr)

    def test_audit_replays_all_frozen_studies(self):
        result = research_toolkit.audit()
        self.assertEqual(
            {key: study["status"] for key, study in result["studies"].items()},
            {"local_auction": "PASS", "codex_authorization": "PASS", "evidence_recovery": "PASS"},
        )

    def test_case_06_is_derived_from_fixture_and_sol_receipts(self):
        branches = research_toolkit.audit()["case_06"]["branches"]
        self.assertEqual(
            [(row["seller_a_quote"], row["seller_b_quote"], row["expiry"]) for row in branches],
            [(86, 97, 1006), (86, 97, 1016)],
        )
        self.assertEqual([row["followup_answer"]["decision"] for row in branches], ["block", "allow"])

    def test_audit_hash_is_independent_of_json_whitespace(self):
        with tempfile.TemporaryDirectory() as temporary:
            copy_root = Path(temporary)
            self._copy_checkout(copy_root)
            summary = copy_root / "results/codex-authorization-01/summary.json"
            data = json.loads(summary.read_bytes())
            summary.write_bytes(json.dumps(data, separators=(",", ":")).encode("utf-8"))
            result = subprocess.run(
                [sys.executable, "-S", "-B", str(copy_root / "research_toolkit.py"), "audit"],
                cwd=copy_root.parent,
                capture_output=True,
                text=True,
                timeout=20,
                check=True,
            )
            self.assertEqual(json.loads(result.stdout), research_toolkit.audit()["studies"])

    def test_tampered_summary_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            copy_root = Path(temporary)
            self._copy_checkout(copy_root)
            summary = copy_root / "results/study-01/summary.json"
            data = json.loads(summary.read_text(encoding="utf-8"))
            data["planned"]["total"] += 1
            summary.write_text(json.dumps(data), encoding="utf-8")
            self._assert_audit_failure(copy_root, "replay differs from frozen summary")

    def test_frozen_summary_rejects_duplicate_keys_and_coerced_numbers(self):
        with tempfile.TemporaryDirectory() as temporary:
            copy_root = Path(temporary)
            self._copy_checkout(copy_root)
            summary = copy_root / "results/study-01/summary.json"
            original = summary.read_text(encoding="utf-8")
            data = json.loads(original)
            for bad in (True, 1.0):
                with self.subTest(schema_version=bad):
                    summary.write_text(json.dumps({**data, "schema_version": bad}), encoding="utf-8")
                    self._assert_audit_failure(copy_root, "replay differs from frozen summary")

            summary.write_text('{"schema_version":0,' + original.lstrip()[1:], encoding="utf-8")
            self._assert_audit_failure(copy_root, "duplicate JSON key")

    def test_copied_checkout_rejects_changed_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            copy_root = Path(temporary)
            self._copy_checkout(copy_root)
            source = copy_root / "auction.py"
            source.write_bytes(source.read_bytes() + b"\n# Unregistered source change.\n")
            self._assert_audit_failure(copy_root, "frozen source, inputs, or requests changed")


if __name__ == "__main__":
    unittest.main()
