import json,tempfile,unittest
from pathlib import Path
from server.campaigns import CampaignError,CampaignStore,build_campaign,compatible,migrate_legacy_dataset,migrate_legacy_experiment,portable,trace_identity_graph,validate_campaign
class CampaignTests(unittest.TestCase):
 def test_state_machine_and_human_decision(self):
  with tempfile.TemporaryDirectory() as d:
   s=CampaignStore(d); c=build_campaign(pack_id="p",pack_fingerprint="pf",baseline_release_id="r1",query_identity="q",gates={"minimum_reviewed":1}); c["readiness_snapshot"]={"reviewed_count":1}; c["campaign_id"]=__import__('server.campaigns',fromlist=['_id'])._id(c); s.save(c)
   for state in ("validating","ready","running","review_required"): c=s.transition(c["campaign_id"],state)
   c=s.decide(c["campaign_id"],"promote","reviewer-1"); self.assertEqual("decided",c["state"])
 def test_incompatible_identities_rejected(self):
  c=build_campaign(pack_id="p",pack_fingerprint="pf",baseline_release_id="r1",query_identity="q")
  with self.assertRaisesRegex(CampaignError,"pack"):
   compatible(c,{"pack_fingerprint":"other","query_identity":"q","corpus_release_id":"r1"})
 def test_stale_or_coverage_blocks_promotion(self):
  with tempfile.TemporaryDirectory() as d:
   s=CampaignStore(d); c=build_campaign(pack_id="p",pack_fingerprint="pf",baseline_release_id="r1",query_identity="q",gates={"minimum_reviewed":2}); c["state"]="review_required"; c["readiness_snapshot"]={"reviewed_count":1}; c["campaign_id"]=__import__('server.campaigns',fromlist=['_id'])._id(c); s.save(c)
   with self.assertRaisesRegex(CampaignError,"coverage"): s.decide(c["campaign_id"],"promote","human")
 def test_pack_roots_and_portable_privacy(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d); pack=root/"pack.json"; pack.write_text(json.dumps({"pack_id":"p","episodes":[{}],"dataset":{"queries":[{"human_reviewed":True,"adjudication_state":"accepted"}]}}),encoding="utf-8")
   self.assertTrue(CampaignStore(root/"store",[root]).import_pack(pack)["readiness"]["ready"])
   self.assertNotIn("C:\\\\private",json.dumps(portable({"path":"C:\\private\\x","raw_conversation":"secret"})))
 def test_identity_graph_links_chain(self):
  graph=trace_identity_graph([{"correction_set_id":"c","producer":{"name":"t"}},{"delta_id":"d","correction_set_ids":["c"],"producer":{"name":"r"}}]); self.assertIn({"parent":"c","child":"d"},graph["edges"])
 def test_fixture_and_legacy_migrations(self):
  fixture=json.loads((Path(__file__).parent/"fixtures/contracts/evaluation-campaign-v1/valid.json").read_text(encoding="utf-8")); validate_campaign(fixture)
  self.assertTrue(migrate_legacy_dataset({"dataset_id":"d"})["migration"]["reduced_readiness"])
  self.assertEqual("legacy-unpinned",migrate_legacy_experiment({"run_id":"r"})["corpus_release_id"])
if __name__=="__main__": unittest.main()
