"""The bundled policy is an exact host-owned identity, not editable instructions."""

import hashlib
from importlib.resources import files
import json
import unittest

from compliance_agent.policy import PolicyError, decode_policy


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.raw = files("compliance_agent").joinpath("resources/policy.json").read_bytes()
        self.document = json.loads(self.raw)

    def test_validated_policy_hashes_exact_bytes(self):
        policy = decode_policy(self.raw)
        self.assertEqual(policy.sha256, hashlib.sha256(self.raw).hexdigest())
        self.assertNotEqual(decode_policy(self.raw + b"\n").sha256, policy.sha256)
        self.assertEqual(policy.to_dict()["rule_id"], "LSL001")

    def test_missing_extra_and_duplicate_fields_are_rejected(self):
        for key in self.document:
            document = self.document.copy()
            del document[key]
            with self.subTest(missing=key), self.assertRaises(PolicyError):
                decode_policy(json.dumps(document).encode())
        with self.assertRaises(PolicyError):
            decode_policy(json.dumps({**self.document, "exception": "approved"}).encode())
        with self.assertRaises(PolicyError):
            decode_policy(self.raw.rstrip()[:-1] + b',"version":"1.0.0"}')

    def test_wrong_types_and_unsupported_values_are_rejected(self):
        for key in self.document:
            for value in (None, True, False, 1.0, [], {}, "altered", 2):
                document = {**self.document, key: value}
                with self.subTest(key=key, value=value), self.assertRaises(PolicyError):
                    decode_policy(json.dumps(document).encode())

    def test_malformed_nonobject_and_oversized_policy_are_rejected(self):
        for raw in (b"", b"\xff", b"[]", b"null", b"42", b"{", b" " * 4097):
            with self.subTest(raw=raw[:20]), self.assertRaises(PolicyError):
                decode_policy(raw)
        at_bound = self.raw + b" " * (4096 - len(self.raw))
        self.assertEqual(decode_policy(at_bound).sha256, hashlib.sha256(at_bound).hexdigest())
        with self.assertRaises(PolicyError):
            decode_policy(at_bound + b" ")


if __name__ == "__main__":
    unittest.main()
