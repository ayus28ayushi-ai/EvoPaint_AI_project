import json

from contracts.conformance.session_suite import SessionConformance
from contracts.definitions import commands
from tests.session.helpers import FakeClock, build_session


class TestSession(SessionConformance):
    def make_session(self, panels=2, max_evaluations=20_000):
        return build_session(panels, max_evaluations)

    def test_painting_param_reaches_the_problem(self):
        s = self.make_session()
        s.send(commands.set_param(1, "painting", "max_shape_size", 0.7))
        s.tick(0.1)
        assert s.panels[1].problem.painting["max_shape_size"] == 0.7
        assert s.panel_info(1).params["max_shape_size"] == 0.7

    def test_out_of_range_values_are_clamped(self):
        s = self.make_session()
        s.send(commands.set_param(0, "algorithm", "batch_size", 500))
        s.send(commands.set_speed(0, 999999))
        s.tick(0.1)
        assert s.panel_info(0).params["batch_size"] == 20
        assert s.panel_info(0).speed == 10000

    def test_bad_commands_do_not_crash(self):
        s = self.make_session()
        s.send(commands.set_speed(9, 100))
        s.send(commands.set_param(0, "algorithm", "nope", 1))
        s.send(commands.trigger_action(0, "nope"))
        s.tick(0.1)
        assert s.status() == "running"

    def test_slow_machine_is_throttled(self):
        s = build_session(panels=1, clock=FakeClock(step=0.01))
        s.send(commands.set_speed(0, 10000))
        s.tick(0.1)
        assert s.panel_info(0).throttled
        event = self.events_of(s, "panel_throttled")[0]
        assert event.payload["requested_speed"] == 10000
        assert event.payload["achieved_speed"] < 10000

    def test_injection_is_tracked_in_the_record(self):
        s = self.make_session(panels=1)
        self.run_ticks(s, 5)
        s.send(commands.inject(count=8))
        self.run_ticks(s, 200)
        outcome = s.finish().results[0].outcome
        assert len(outcome.injections) == 1
        assert outcome.injections[0].evaluation_index > 0

    def test_record_has_images_and_events(self):
        s = self.make_session()
        self.run_ticks(s, 10)
        record = s.finish()
        assert record.images["target"].size == (512, 512)
        assert set(record.images) == {"target", "result_0", "result_1"}
        assert set(record.shapes) == {0, 1}
        assert record.events[-1].type == "run_finished"

    def test_one_batch_is_shared_by_every_panel(self):
        s = self.make_session(panels=3)
        received = []
        for p in s.panels:
            real = p.algo.inject
            p.algo.inject = lambda batch, real=real: (received.append(batch), real(batch))
        self.run_ticks(s, 3)
        s.send(commands.inject(count=8))
        s.tick(0.1)
        assert len(received) == 3
        assert received[0] is received[1] is received[2]

    def test_record_converts_to_json(self):
        s = self.make_session()
        self.run_ticks(s, 10)
        s.send(commands.inject(count=4))
        self.run_ticks(s, 10)
        data = json.loads(json.dumps(s.finish().to_dict()))
        assert data["config"]["max_evaluations"] == 20_000
        assert set(data["outcomes"]) == {"0", "1"}
        assert "final_similarity" in data["outcomes"]["0"]
        assert any(e["type"] == "shapes_injected" for e in data["events"])
