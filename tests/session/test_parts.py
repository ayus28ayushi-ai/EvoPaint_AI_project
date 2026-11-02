from contracts.definitions import MAX_HISTORY_POINTS, MilestoneHit, Outcome, Problem, Snapshot
from session.history import History
from session.leaderboard import build_leaderboard
from session.milestones import MilestoneTracker
from session.registry import get_algorithm, list_algorithms
from session.scheduler import Scheduler
from session.scoring import best_index, pick_awards, pick_winners


def snap(evaluations=0, best=50.0):
    return Snapshot("x", 0, evaluations, 1.0, best, 1.0, best, None, None, evaluations, evaluations // 2)


def outcome(final=50.0, hit80=None, worse=0, efficiency=0.0, auc=0.0):
    hit = None if hit80 is None else MilestoneHit(hit80, 1.0)
    return Outcome(final, 100, 1.0, hit, None, None, auc, efficiency, 0.5, worse, 0)


class TestHistory:
    def test_stays_under_the_cap_and_keeps_the_latest_point(self):
        h = History()
        for i in range(MAX_HISTORY_POINTS * 3):
            h.add(snap(evaluations=i))
        assert len(h.points) <= MAX_HISTORY_POINTS
        assert h.points[-1].evaluations == MAX_HISTORY_POINTS * 3 - 1
        evals = [p.evaluations for p in h.points]
        assert evals == sorted(evals)

    def test_sample_respects_max_points(self):
        h = History()
        for i in range(100):
            h.add(snap(evaluations=i))
        assert len(h.sample(7)) == 7
        assert h.sample(7)[-1].evaluations == 99
        assert len(h.sample(1)) == 1


class TestMilestones:
    def test_each_level_fires_once(self):
        t = MilestoneTracker()
        assert t.update(85.0, 10, 1.0) == [80]
        assert t.update(85.0, 20, 2.0) == []
        assert t.update(96.0, 30, 3.0) == [90, 95]
        assert t.hits[80].evaluations == 10


class TestScheduler:
    def test_fractions_carry_over(self):
        s = Scheduler(1)
        assert s.owed(0, 15, 0.1) == 1
        s.settle(0, 1)
        assert s.owed(0, 15, 0.1) == 2

    def test_overshoot_is_paid_back(self):
        s = Scheduler(1)
        assert s.owed(0, 100, 0.1) == 10
        s.settle(0, 25)
        assert s.owed(0, 100, 0.1) == 0

    def test_backlog_is_dropped_when_throttled(self):
        s = Scheduler(1)
        s.owed(0, 1000, 0.1)
        assert s.settle(0, 10) is True
        assert s.owed(0, 1000, 0.1) == 100


class TestLeaderboard:
    def test_ranks_and_changes(self):
        snaps = [snap(best=60.0), snap(best=70.0), snap(best=70.0)]
        board = build_leaderboard(snaps, [False] * 3, [{}] * 3, {0: 1, 1: 3, 2: 2})
        assert [(e.rank, e.panel_index) for e in board] == [(1, 1), (2, 2), (3, 0)]
        assert [e.rank_change for e in board] == [2, 0, -2]


class TestScoring:
    def test_ties_go_to_the_lowest_panel(self):
        assert best_index({2: 5.0, 1: 5.0}, largest=True) == 1
        assert best_index({}, largest=True) is None

    def test_winners_and_awards(self):
        outcomes = [outcome(final=90, hit80=500, worse=3), outcome(final=95, hit80=300, worse=1)]
        winners = pick_winners(outcomes)
        assert winners["fastest_to_80"] == 1 and winners["best_final"] == 1
        assert winners["fastest_to_90"] is None and winners["fastest_recovery"] is None
        awards = pick_awards(outcomes, winners)
        assert awards["risk_taker"] == 0 and awards["sprinter"] == 1
        assert "comeback_kid" not in awards

    def test_one_panel_is_solo_artist(self):
        assert pick_awards([outcome()], pick_winners([outcome()])) == {"solo_artist": 0}


class TestRegistry:
    def test_finds_stochastic_hc(self):
        infos = {i.id: i for i in list_algorithms()}
        info = infos["stochastic_hc"]
        assert {p.name for p in info.param_specs} == {"step_scale", "batch_size"}
        assert info.action_specs == ()

    def test_unknown_id_names_the_known_ones(self):
        try:
            get_algorithm("nope")
        except KeyError as error:
            assert "stochastic_hc" in str(error)
        else:
            raise AssertionError("expected KeyError")


class TestEngineContract:
    def test_session_only_calls_methods_the_problem_contract_declares(self):
        used = {
            "initial_state", "evaluate", "propose", "similarity", "render", "target_image",
            "make_injection", "apply_injection", "state_to_dict", "param_specs", "set_param",
            "shape_count",
        }  # fmt: skip
        assert used <= set(Problem.__abstractmethods__)
