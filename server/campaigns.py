"""Evaluation-campaign-v1 persistence, readiness, triage, and identity graph."""
from __future__ import annotations
import hashlib, json, os, re, tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

CONTRACT="evaluation-campaign-v1"; MUTABLE={"notes","display_label","ui_state","campaign_id"}
STATES=("draft","validating","ready","running","review_required","decided","archived")
class CampaignError(ValueError): pass
def _canonical(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")
def _id(v,prefix="campaign"):
 return prefix+"_"+hashlib.sha256(_canonical({k:deepcopy(x) for k,x in v.items() if k not in MUTABLE})).hexdigest()
def validate_campaign(v:Mapping[str,Any])->None:
 if v.get("contract_version")!=CONTRACT: raise CampaignError("unsupported campaign contract")
 if v.get("campaign_id")!=_id(v): raise CampaignError("campaign identity mismatch")
 if v.get("state") not in STATES: raise CampaignError("invalid campaign state")
 if v.get("decision") and not v["decision"].get("human_reviewer"): raise CampaignError("only human action can create a promotion decision")

def build_campaign(*,pack_id:str,pack_fingerprint:str,baseline_release_id:str,candidate_release_id:str|None=None,query_identity:str="",gates:Mapping[str,Any]|None=None)->dict[str,Any]:
 value={"contract_version":CONTRACT,"producer":{"name":"RAGScope","contract_version":"1"},"pack_id":pack_id,"pack_fingerprint":pack_fingerprint,"baseline_release_id":baseline_release_id,"candidate_release_id":candidate_release_id,"query_identity":query_identity,"run_ids":[],"readiness_snapshot":{},"gates":dict(gates or {}),"results":{},"stale_judgment_ids":[],"decision":None,"rollback_recommendation":None,"state":"draft"}
 value["campaign_id"]=_id(value); return value

def compatible(campaign:Mapping[str,Any],run:Mapping[str,Any])->None:
 checks=(("pack_fingerprint","pack_fingerprint"),("query_identity","query_identity"))
 for left,right in checks:
  if campaign.get(left)!=run.get(right): raise CampaignError(f"incompatible {left}")
 releases={campaign.get("baseline_release_id"),campaign.get("candidate_release_id")}
 if run.get("corpus_release_id") not in releases: raise CampaignError("incompatible corpus release identity")

def portable(value:Mapping[str,Any])->dict[str,Any]:
 result=deepcopy(dict(value)); result.pop("notes",None); result.pop("private_text",None)
 def scrub(v):
  if isinstance(v,dict): return {k:scrub(x) for k,x in v.items() if k not in {"raw_conversation","private_text","local_path"}}
  if isinstance(v,list): return [scrub(x) for x in v]
  if isinstance(v,str) and (re.match(r"^[A-Za-z]:[\\/]",v) or v.startswith("/")): return "[LOCAL_PATH_REDACTED]"
  return v
 return scrub(result)

def trace_identity_graph(artifacts:list[Mapping[str,Any]])->dict[str,Any]:
 nodes={}; edges=[]; stale=[]
 for artifact in artifacts:
  identity=next((artifact.get(k) for k in ("correction_set_id","delta_id","release_id","trace_id","feedback_id","campaign_id") if artifact.get(k)),None)
  if not identity: continue
  nodes[str(identity)]={"contract_version":artifact.get("contract_version"),"owner":artifact.get("producer",{}).get("name")}
  parents=[]
  for key in ("correction_set_ids","applied_delta_ids","source_trace_id","corpus_release_id","parent_release_id"):
   item=artifact.get(key); parents.extend(item if isinstance(item,list) else [item] if item else [])
  edges.extend({"parent":str(parent),"child":str(identity)} for parent in parents)
  stale.extend({"judgment_id":str(j),"reason":f"affected by {identity}"} for j in artifact.get("stale_judgment_ids",[]))
 return {"nodes":nodes,"edges":edges,"stale_judgments":stale}

def migrate_legacy_dataset(dataset:Mapping[str,Any])->dict[str,Any]:
 value=deepcopy(dict(dataset)); fingerprint=hashlib.sha256(_canonical(value)).hexdigest()
 return {"format":"podcast-evaluation-pack-v1","pack_id":"legacy_pack_"+fingerprint,"episodes":[],"dataset":value,"migration":{"reduced_readiness":True,"reason":"episode references require local review"}}

def migrate_legacy_experiment(experiment:Mapping[str,Any])->dict[str,Any]:
 value=deepcopy(dict(experiment))
 return {"run_id":str(value.get("run_id") or _id(value,"legacy_run")),"pack_fingerprint":str(value.get("pack_fingerprint") or value.get("judged_dataset_fingerprint") or "legacy-unknown"),"corpus_release_id":str(value.get("corpus_release_id") or "legacy-unpinned"),"query_identity":str(value.get("query_identity") or value.get("query_set_sha256") or "legacy-unknown"),"legacy_source":value}

class CampaignStore:
 def __init__(self,root:str|Path,selected_roots:list[str|Path]|None=None):
  self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True); self.selected_roots=[Path(p).resolve() for p in (selected_roots or [])]
 def _path(self,campaign_id):
  if not re.fullmatch(r"campaign_[0-9a-f]{64}",campaign_id): raise CampaignError("invalid campaign ID")
  return self.root/f"{campaign_id}.json"
 def save(self,value:Mapping[str,Any]):
  validate_campaign(value); path=self._path(str(value["campaign_id"])); fd,tmp=tempfile.mkstemp(dir=self.root,suffix=".tmp")
  with os.fdopen(fd,"w",encoding="utf-8") as f: json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2); f.write("\n")
  os.replace(tmp,path); return deepcopy(dict(value))
 def load(self,campaign_id): return json.loads(self._path(campaign_id).read_text(encoding="utf-8"))
 def list(self): return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(self.root.glob("campaign_*.json"))]
 def transition(self,campaign_id,state):
  value=self.load(campaign_id); current=STATES.index(value["state"]); target=STATES.index(state)
  if target!=current+1: raise CampaignError(f"invalid campaign transition {value['state']} -> {state}")
  value["state"]=state; value["campaign_id"]=_id(value); return self.save(value)
 def import_pack(self,path:str|Path):
  candidate=Path(path).resolve()
  if not self.selected_roots or not any(candidate==root or root in candidate.parents for root in self.selected_roots): raise CampaignError("pack path is outside selected local roots")
  value=json.loads(candidate.read_text(encoding="utf-8")); dataset=value.get("dataset",{}); queries=dataset.get("queries",[]); episodes=value.get("episodes",[])
  reviewed=sum(1 for q in queries if q.get("human_reviewed") and q.get("adjudication_state")=="accepted")
  return {"pack_id":value.get("pack_id"),"pack_fingerprint":hashlib.sha256(_canonical(value)).hexdigest(),"readiness":{"episode_count":len(episodes),"query_count":len(queries),"reviewed_count":reviewed,"ready":bool(episodes and queries and reviewed==len(queries))}}
 def register_run(self,campaign_id,run):
  value=self.load(campaign_id); compatible(value,run); run_id=str(run["run_id"])
  if run_id not in value["run_ids"]: value["run_ids"].append(run_id)
  value["campaign_id"]=_id(value); return self.save(value)
 def decide(self,campaign_id,decision,reviewer):
  value=self.load(campaign_id)
  if value["state"]!="review_required": raise CampaignError("campaign is not ready for a decision")
  if value.get("stale_judgment_ids"): raise CampaignError("stale judgments block promotion")
  required=int(value.get("gates",{}).get("minimum_reviewed",0)); reviewed=int(value.get("readiness_snapshot",{}).get("reviewed_count",0))
  if reviewed<required: raise CampaignError("insufficient reviewed coverage blocks promotion")
  value["decision"]={"value":decision,"human_reviewer":reviewer}; value["state"]="decided"; value["campaign_id"]=_id(value); return self.save(value)
