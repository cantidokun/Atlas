import unittest

from controller_state import (
    ControllerState,
    TARGET_MIDPOINT,
    establish_target,
    next_required_action,
    record_after,
    record_before,
    record_write,
    required_moves,
)


BEFORE = {
    "object_a": {
        "name": "Goal_Left_post",
        "type": "MESH",
        "location": [0.0, 5.44, 0.0],
        "dimensions": [2.0, 2.0, 2.0],
    },
    "object_b": {
        "name": "Goal_Right_Post",
        "type": "MESH",
        "location": [0.0, -5.164, 0.0],
        "dimensions": [2.0, 2.0, 2.0],
    },
    "midpoint": [0.0, 0.138, 0.0],
}


class ControllerStateTests(unittest.TestCase):
    def make_state(self):
        return ControllerState(
            file_name="goalpost_test.blend",
            object_a_name="Goal_Left_post",
            object_b_name="Goal_Right_Post",
        )

    def _complete_writes(self, state):
        record_write(
            state,
            "Goal_Left_post",
            [0.0, 5.302, 0.0],
            {"status": "moved", "object_name": "Goal_Left_post"},
        )
        record_write(
            state,
            "Goal_Right_Post",
            [0.0, -5.302, 0.0],
            {"status": "moved", "object_name": "Goal_Right_Post"},
        )

    def test_before_state_calculates_both_target_locations(self):
        state = self.make_state()
        record_before(state, BEFORE)

        self.assertEqual(state.phase, "TARGET")
        self.assertEqual(state.target["midpoint"], TARGET_MIDPOINT)
        self.assertEqual(state.target["adjustment"], [0.0, -0.138, 0.0])
        self.assertEqual(state.target["object_a_location"], [0.0, 5.302, 0.0])
        self.assertEqual(state.target["object_b_location"], [0.0, -5.302, 0.0])

    def test_controller_requires_first_write_then_second_write(self):
        state = self.make_state()
        record_before(state, BEFORE)

        first = next_required_action(state)
        self.assertEqual(first["kind"], "write")
        self.assertEqual(first["arguments"]["object_name"], "Goal_Left_post")

        record_write(
            state,
            "Goal_Left_post",
            [0.0, 5.302, 0.0],
            {"status": "moved", "object_name": "Goal_Left_post"},
        )

        second = next_required_action(state)
        self.assertEqual(second["kind"], "write")
        self.assertEqual(second["arguments"]["object_name"], "Goal_Right_Post")
        self.assertEqual(len(required_moves(state)), 1)

    def test_controller_requires_after_verification_after_all_writes(self):
        state = self.make_state()
        record_before(state, BEFORE)
        self._complete_writes(state)

        self.assertEqual(next_required_action(state)["kind"], "verification")

        after = {
            **BEFORE,
            "object_a": {**BEFORE["object_a"], "location": [0.0, 5.302, 0.0]},
            "object_b": {**BEFORE["object_b"], "location": [0.0, -5.302, 0.0]},
            "midpoint": [0.0, 0.0, 0.0],
        }

        record_after(state, after)

        self.assertEqual(state.phase, "AFTER")
        self.assertTrue(state.complete)
        self.assertEqual(next_required_action(state)["kind"], "complete")

    def test_after_with_correct_midpoint_but_wrong_object_location_is_rejected(self):
        state = self.make_state()
        record_before(state, BEFORE)
        self._complete_writes(state)

        after = {
            **BEFORE,
            "object_a": {**BEFORE["object_a"], "location": [0.0, 5.302, 0.0]},
            "object_b": {**BEFORE["object_b"], "location": [0.0, -5.0, 0.0]},
            "midpoint": [0.0, 0.0, 0.0],
        }
        with self.assertRaisesRegex(ValueError, "AFTER evidence"):
            record_after(state, after)

        self.assertFalse(state.complete)
        self.assertIsNone(state.after)
        self.assertEqual(next_required_action(state)["kind"], "verification")

    def test_after_requires_valid_target_locations_not_just_midpoint(self):
        state = self.make_state()
        record_before(state, BEFORE)
        self._complete_writes(state)

        after = {
            **BEFORE,
            "object_a": {**BEFORE["object_a"], "location": [0.0, 5.302, 0.0]},
            "object_b": {**BEFORE["object_b"], "location": [0.0, -5.302, 0.0]},
            "midpoint": [0.0, 0.0, 0.001],
        }
        with self.assertRaisesRegex(ValueError, "AFTER evidence"):
            record_after(state, after)

        self.assertFalse(state.complete)
        self.assertIsNone(state.after)
        self.assertEqual(next_required_action(state)["kind"], "verification")

    def test_failed_write_does_not_advance_state(self):
        state = self.make_state()
        record_before(state, BEFORE)

        record_write(
            state,
            "Goal_Left_post",
            [0.0, 5.302, 0.0],
            {"status": "error", "error": "test failure"},
        )

        self.assertEqual(len(state.writes), 0)
        self.assertEqual(next_required_action(state)["kind"], "write")


if __name__ == "__main__":
    unittest.main()
