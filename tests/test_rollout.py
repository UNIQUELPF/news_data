import unittest

from pipeline.rollout import resolve_rollout_profile


class RolloutTest(unittest.TestCase):
    def test_resolve_rollout_profile_defaults_to_small(self):
        profile = resolve_rollout_profile(None)
        self.assertEqual(profile["stage"], "small")
        self.assertEqual(profile["translate_limit"], 25)
        self.assertEqual(profile["embed_limit"], 25)

    def test_resolve_rollout_profile_known_stage(self):
        profile = resolve_rollout_profile("medium")
        self.assertEqual(profile["stage"], "medium")
        self.assertEqual(profile["translate_limit"], 100)
        self.assertEqual(profile["embed_limit"], 100)

    def test_resolve_rollout_profile_unknown_stage_falls_back(self):
        profile = resolve_rollout_profile("weird")
        self.assertEqual(profile["stage"], "small")


if __name__ == "__main__":
    unittest.main()
