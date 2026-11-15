import base64
import io
import unittest
from unittest.mock import patch

import study


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.case = study.canary("gemma")
        self.reply = {"model": study.MODELS["gemma"][0], "done": True, "done_reason": "stop",
                      "message": {"role": "assistant", "content": '{"decision":"ready"}'}}

    def test_request_has_no_case_metadata_or_tool_dispatch(self):
        request = study.decode(study.request_bytes({**self.case, "truth": "PRIVATE_TRUTH"}))
        self.assertEqual(request["tools"], [])
        self.assertEqual(request["messages"], [{"role": "user", "content": self.case["prompt"]}])
        self.assertIs(request["think"], False)

    def test_bad_shape_never_becomes_a_grade(self):
        self.assertEqual(study.parse_decision(self.case, 200, study.encode(self.reply)), "ready")
        for changes in ({"model": "other"}, {"done": 1}, {"done_reason": "length"},
                        {"message": {"role": "assistant", "content": '{"decision":"ready","decision":"ready"}'}},
                        {"message": {**self.reply["message"], "tool_calls": [{"name": "anything"}]}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                study.parse_decision(self.case, 200, study.encode({**self.reply, **changes}))

    def test_transport_failure_is_persisted_without_retry(self):
        reservations, receipts = io.BytesIO(), io.BytesIO()
        with patch("study.http_request", side_effect=TimeoutError) as request:
            self.assertEqual(study.record_call(self.case, reservations, receipts, 5), ("operational_unknown", None))
        self.assertEqual(request.call_count, 1)
        reservation, receipt = map(lambda handle: study.decode(handle.getvalue()), (reservations, receipts))
        self.assertEqual(receipt["request_sha256"], reservation["request_sha256"])
        self.assertEqual(receipt["error"], "TimeoutError")

    def test_raw_response_hash_is_verified_before_parse(self):
        raw = study.encode(self.reply)
        receipt = {"body": base64.b64encode(raw).decode("ascii"), "body_sha256": "wrong", "http_status": 200}
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            study.evaluate_receipt(self.case, receipt)


if __name__ == "__main__":
    unittest.main()
