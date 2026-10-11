"""Offline schedules and actual client arrival contracts in both installs."""
import os
import json
import unittest
from unittest.mock import Mock, patch

import npc_activity as activity
from test_cameo_clothing import ROOTS, load
from test_cameo_nearby import NearbyTests
from test_scene_memory import module_at


class ActivityTests(unittest.TestCase):
    def test_disabled_server_authority_and_strict_config(self):
        for root in ROOTS:
            server = module_at(root, "main")
            scene = self.scene()
            scene.update(invitable=["mi", "cs"], capacity=3, max_extra=6,
                         npc_activity_enabled=True,
                         pending_calls={"mi": dict(location_id="square", wait_turns=2)})
            with patch.object(server, "cfg", {"npc_activity_enabled": False}), \
                    patch.object(server, "scene_event"), patch("scene_memory.ingest"), \
                    patch("story_events.acknowledge_direct"), \
                    patch("story_events.direct_request", return_value=None), \
                    patch("llm_client.chat", side_effect=AssertionError("paid call")):
                out = server.chat(dict(character="sl", text="Мику, подойди!", scene=scene))
            self.assertEqual(out["cameo"], ["mi"])
            self.assertEqual(out["npc_calls"], [])
            disabled = activity.authoritative(scene, enabled=False)
            self.assertEqual(disabled["activity"], {})
            self.assertEqual(disabled["pending_calls"], {})
            self.assertEqual(activity.prompt(disabled), "")
            self.assertEqual(activity.decide(["mi", "cs"], disabled), (["mi", "cs"], []))
            forged = dict(scene, npc_activity_enabled=False)
            self.assertEqual(activity.decide(["mi"], activity.authoritative(forged))[1][0]["status"], "pending")
            with patch.object(server, "cfg", {}), patch("config_loader.save_config") as save:
                for value in (0, 1, "false", None, []):
                    self.assertFalse(server.config_set(dict(section="", key="npc_activity_enabled", value=value))["ok"])
                save.assert_not_called()
                for value in (False, True):
                    self.assertTrue(server.config_set(dict(section="", key="npc_activity_enabled", value=value))["ok"])
                    self.assertIs(server.cfg["npc_activity_enabled"], value)

    def test_disabled_client_immediate_stale_calls_and_no_pending(self):
        for root in ROOTS:
            e = self.client(root)
            e["es_ai_read_cameo_settings"] = Mock(return_value=dict(e["ES_AI_CAMEO_DEFAULTS"],
                npc_activity_enabled=False, cameo_freq=0, cameo_ctx=0, cameo_interject=0))
            e["ES_AI_ACTIVITY_PENDING"]["mz"] = dict(location_id="square", wait_turns=2)
            response = dict(ok=True, cameo_requested=True, npc_calls=[dict(id="mi", status="pending",
                reason="rehearsal", wait_turns=2, location_id="square")])
            e["es_ai_try_cameo"]("sl", "Мику, подойди!", response)
            e["es_ai_cameo_line"].assert_called_once()
            self.assertEqual(e["es_ai_cameo_line"].call_args.args[0], "mi")
            self.assertEqual(e["ES_AI_ACTIVITY_PENDING"], {})
            e["es_ai_activity_notice"].assert_not_called()
            e["es_ai_maybe_cameo"].assert_not_called()
            snapshot = e["es_ai_scene_snapshot"]("sl")
            self.assertIs(snapshot["npc_activity_enabled"], False)
            self.assertEqual(snapshot.get("activity", {}), {})
            self.assertEqual(snapshot.get("pending_calls", {}), {})
            self.assertEqual(e["es_ai_activity_bias"]("cs"), 1.0)

    def test_disabled_random_pool_does_not_consult_schedules(self):
        for root in ROOTS:
            e = self.client(root)
            e["es_ai_read_cameo_settings"] = Mock(return_value=dict(e["ES_AI_CAMEO_DEFAULTS"],
                npc_activity_enabled=False))
            e["ES_AI_CAMEO_BY_LOC"]["square"] = ["mi"]
            e["ES_AI_CAMEO_CD"][0] = 0
            e["es_ai_activity_bias"] = Mock(side_effect=AssertionError("schedule filter"))
            # Load the real random picker instead of this fixture's delivery stub.
            original = e["es_ai_read_cameo_settings"]
            enabled = e["es_ai_cameo_on"]
            load(os.path.join(root, "es_ai_cameo.rpy"), e)
            e["es_ai_read_cameo_settings"] = original
            e["es_ai_cameo_on"] = enabled
            e["ES_AI_LOC_CUR"][:] = ["square"]
            e["ES_AI_CAMEO_BY_LOC"]["square"] = ["mi"]
            e["ES_AI_CAMEO_CD"][0] = 0
            with patch.object(e["_es_random"], "random", return_value=0):
                self.assertEqual(e["es_ai_maybe_cameo"]("sl", False, chance=1), ["mi"])
            e["es_ai_activity_bias"].assert_not_called()

    def scene(self, location="square", present=None):
        return activity.authoritative(dict(enabled=True, location_id=location,
            present=present or [], nearby=[], destination_nearby={},
            activity={cid: {} for cid in ("mi", "cs", "mz", "dv")}), {"phase": "day"})

    def test_schedule_clock_bounds_and_client_parity(self):
        for root in ROOTS:
            e = NearbyTests().environment(root)
            load(os.path.join(root, "es_ai_activity.rpy"), e)
            for phase, time in (("morning", "08:00"), ("day", "14:00"), ("sunset", "20:00"), ("night", "23:00")):
                e["ES_AI_TIME"][0] = phase
                for cid in ("mi", "cs", "mz", "dv", "un", "sl", "mt", "us", "el", "sh", "uv"):
                    state = activity.schedule(cid, dict(enabled=True, time=time, phase="wrong"))
                    self.assertEqual(state, e["es_ai_activity_schedule"](cid))
                    self.assertTrue(1 <= state["eta_turns"] <= 3)
                    self.assertEqual(state, activity.schedule(cid, dict(phase=phase)))

    def test_local_bypass_and_duty_refusal(self):
        ready, calls = activity.decide(["mi", "cs"], self.scene(present=["mi"]))
        self.assertEqual(ready, ["mi"])
        self.assertEqual([c["status"] for c in calls], ["ready", "refused"])
        self.assertEqual(activity.decide(["cs"], self.scene("aidpost_inside"))[0], ["cs"])
        self.assertEqual(activity.decide(["mi"], self.scene("musclub_inside"))[0], ["mi"])
        self.assertEqual(activity.decide(["mi"], self.scene(present=["mi"]), "beach")[0], ["mi"])
        self.assertEqual(activity.decide(["mi"], {"enabled": True}), (["mi"], []))

    def test_recorded_location_wins(self):
        scene = self.scene()
        scene["destination_nearby"] = {"beach": ["mz"]}
        scene = activity.authoritative(scene, {"phase": "day"})
        self.assertEqual(scene["activity"]["mz"]["location"], "beach")
        self.assertEqual(activity.decide(["mz"], scene, "library")[1][0]["status"], "pending")

    def test_pending_repeat_arrival_and_movement(self):
        for root in ROOTS:
            e = NearbyTests().environment(root)
            load(os.path.join(root, "es_ai_activity.rpy"), e)
            notices, calls = [], []
            e["es_ai_activity_notice"] = notices.append
            e["es_ai_cameo_line"] = lambda cid, *a, **k: calls.append((cid, [g["id"] for g in e["ES_AI_SHOWN"]])) or {"reply": "Hi"}
            decision = dict(id="dv", status="pending", reason="resting", wait_turns=2, location_id="square")
            response = dict(ok=True, cameo=[], cameo_requested=True, npc_calls=[decision])
            e["es_ai_try_cameo"]("sl", "Call", response)
            self.assertEqual(calls, [])
            self.assertEqual(len(notices), 1)
            self.assertEqual(e["ES_AI_ACTIVITY_PENDING"]["dv"]["wait_turns"], 2)
            e["es_ai_try_cameo"]("sl", "Failed", dict(ok=False))
            self.assertEqual(e["ES_AI_ACTIVITY_PENDING"]["dv"]["wait_turns"], 2)
            e["es_ai_try_cameo"]("sl", "Call again", response)
            self.assertEqual(e["ES_AI_ACTIVITY_PENDING"]["dv"]["wait_turns"], 1)
            self.assertEqual(len(notices), 1)
            e["es_ai_try_cameo"]("sl", "Wait", dict(ok=True, cameo_requested=True))
            self.assertEqual(calls, [("dv", ["sl", "dv"])])
            self.assertEqual(e["ES_AI_ACTIVITY_PENDING"], {})
            e["ES_AI_ACTIVITY_PENDING"]["us"] = dict(decision, id="us")
            e["es_ai_set_location"]("beach")
            self.assertEqual(e["ES_AI_ACTIVITY_PENDING"], {})

    def test_pending_repeat_server_keeps_eta(self):
        scene = self.scene()
        scene["pending_calls"] = {"mi": dict(location_id="square", wait_turns=1)}
        self.assertEqual(activity.decide(["mi"], scene)[1][0]["wait_turns"], 1)
        scene["pending_calls"]["mi"]["wait_turns"] = 0
        self.assertEqual(activity.decide(["mi"], scene)[0], ["mi"])

    def test_direct_busy_no_model_or_network(self):
        import main
        scene = self.scene()
        scene.update(invitable=["mi", "cs"], capacity=3, max_extra=6)
        with patch("main.scene_event"), patch("scene_memory.ingest"), patch("story_events.acknowledge_direct"), patch("story_events.direct_request", return_value=None), patch("llm_client.chat", side_effect=AssertionError("paid call")):
            out = main.chat(dict(character="sl", text="Мику, подойди!", scene=scene))
        self.assertTrue(out["ok"])
        self.assertTrue(out["suppress_main_reply"])
        self.assertEqual(out["reply"], "")
        self.assertEqual(out["cameo"], [])
        self.assertEqual(out["npc_calls"][0]["status"], "pending")

    def normal_response(self, root, targets, classifier=False, present=None):
        server = module_at(root, "main")
        scene = self.scene(present=present)
        scene.update(invitable=["mi", "cs", "dv"], capacity=3, max_extra=6)
        raw = "(нормально) Попробуем позвать."
        if not classifier:
            raw += " [action:cameo:%s]" % ",".join(targets)
        with patch.object(server, "cfg", {}), patch.object(server, "scene_event"), \
                patch.object(server, "resolve_cameo_intent", return_value=targets) as intent, \
                patch("scene_memory.ingest"), patch("scene_memory.prompt", return_value=""), \
                patch("story_events.acknowledge_direct"), patch("story_events.prepare", return_value=None), \
                patch("story_events.parse_tags", side_effect=lambda raw: (raw, None)), \
                patch("story_events.commit"), patch("conversation.add_exchange"), \
                patch("conversation.build_history_block", return_value=[dict(role="system", content="Scene")]), \
                patch("llm_client.chat", return_value=raw) as model, \
                patch("llm_client.sanitize_in_character", side_effect=lambda raw: raw), \
                patch("llm_client.strip_prompt_leak", side_effect=lambda raw, prompt: raw), \
                patch("threading.Thread"):
            out = server.chat(dict(character="sl", text="Давай пригласим знакомых сюда", scene=scene))
        self.assertEqual(model.call_count, 1)
        self.assertEqual(intent.call_count, int(classifier))
        self.assertTrue(out["ok"])
        self.assertTrue(out["cameo_requested"])
        return json.loads(json.dumps(out))

    def client(self, root):
        e = NearbyTests().environment(root)
        load(os.path.join(root, "es_ai_activity.rpy"), e)
        e["ES_AI_CHARS"].extend((cid, cid, "") for cid in ("mi", "cs", "mz"))
        e["es_ai_activity_notice"] = Mock()
        e["es_ai_cameo_tick"] = Mock()
        e["es_ai_maybe_cameo"] = Mock(return_value=["us"])
        e["es_ai_cameo_line"] = Mock(return_value={"reply": "Here"})
        return e

    def test_normal_chat_json_pending_and_refused_suppress_random(self):
        for root in ROOTS:
            for classifier in (False, True):
                for target, status in (("mi", "pending"), ("cs", "refused")):
                    with self.subTest(root=root, classifier=classifier, status=status):
                        out = self.normal_response(root, [target], classifier)
                        self.assertEqual(out["npc_calls"][0]["status"], status)
                        for legacy in (False, True):
                            response = json.loads(json.dumps(out))
                            if legacy:
                                del response["cameo_requested"]
                            e = self.client(root)
                            e["es_ai_try_cameo"]("sl", "Invite", response)
                            e["es_ai_maybe_cameo"].assert_not_called()
                            e["es_ai_cameo_tick"].assert_not_called()
                            e["es_ai_cameo_line"].assert_not_called()
                            self.assertEqual([g["id"] for g in e["ES_AI_SHOWN"]], ["sl"])
                            if status == "pending":
                                self.assertEqual(e["ES_AI_ACTIVITY_PENDING"][target]["wait_turns"], 2)
                                e["es_ai_try_cameo"]("sl", "Ordinary exchange", {"ok": True})
                                self.assertEqual(e["ES_AI_ACTIVITY_PENDING"][target]["wait_turns"], 1)
                                e["es_ai_maybe_cameo"].assert_called_once()

    def test_normal_chat_json_mixed_ready_pending(self):
        for root in ROOTS:
            for classifier in (False, True):
                out = self.normal_response(root, ["mi", "dv"], classifier, present=["dv"])
                self.assertEqual(out["cameo"], ["dv"])
                self.assertEqual([c["status"] for c in out["npc_calls"]], ["pending", "ready"])
                e = self.client(root)
                e["es_ai_cameo_enter"]("dv", "normal", stay=True)
                e["es_ai_try_cameo"]("sl", "Invite", out)
                self.assertEqual(e["es_ai_cameo_line"].call_args.args[0], "dv")
                e["es_ai_cameo_line"].assert_called_once()
                e["es_ai_maybe_cameo"].assert_not_called()
                self.assertEqual(e["ES_AI_ACTIVITY_PENDING"]["mi"]["wait_turns"], 2)

    def test_defensive_validation_and_initiative_scope(self):
        valid = dict(id="mi", status="pending", reason="rehearsal", wait_turns=2, location_id="square")
        for root in ROOTS:
            for change in ({"id": "unknown"}, {"status": "invalid"}, {"wait_turns": True},
                           {"wait_turns": 4}, {"location_id": "beach"}, {"reason": None}):
                e = self.client(root)
                e["es_ai_try_cameo"]("sl", "Invite", dict(ok=True, npc_calls=[dict(valid, **change)]))
                e["es_ai_maybe_cameo"].assert_called_once()
            e = self.client(root)
            e["es_ai_try_cameo"]("sl", "", dict(ok=True, npc_calls=[valid]))
            e["es_ai_maybe_cameo"].assert_called_once()
            self.assertEqual(e["ES_AI_ACTIVITY_PENDING"]["mi"]["wait_turns"], 2)


if __name__ == "__main__":
    unittest.main()
