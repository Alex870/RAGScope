"""Production parsers for producer-owned ecosystem fixtures."""
import hashlib,json
from pathlib import Path
from typing import Any
class ArtifactContractError(ValueError): pass
def _canonical(v:Any): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")
def parse_correction(path:str|Path)->dict[str,Any]:
 value=json.loads(Path(path).read_text(encoding="utf-8")); manifest=value.get("manifest",value); transcript=value.get("transcript")
 if manifest.get("contract_version")!="correction-manifest-v1": raise ArtifactContractError("unsupported correction")
 if transcript and hashlib.sha256(_canonical(transcript)).hexdigest()!=manifest.get("source_transcript_hash"): raise ArtifactContractError("stale transcript hash")
 return manifest
def parse_delta(path:str|Path)->dict[str,Any]:
 value=json.loads(Path(path).read_text(encoding="utf-8"))
 if value.get("contract_version")!="processed-delta-v1": raise ArtifactContractError("unsupported processed delta")
 if any(x not in value.get("reasons",{}) for x in value.get("changed_document_ids",[])+value.get("removed_document_ids",[])): raise ArtifactContractError("delta reason missing")
 return value
def parse_release(path:str|Path)->dict[str,Any]:
 value=json.loads(Path(path).read_text(encoding="utf-8"))
 if value.get("contract_version")!="corpus-release-v1": raise ArtifactContractError("unsupported corpus release")
 if not value.get("release_id"): raise ArtifactContractError("release identity missing")
 return value
