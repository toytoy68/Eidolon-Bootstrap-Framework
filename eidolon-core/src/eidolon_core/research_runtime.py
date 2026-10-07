# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : research_runtime.py
# Description : Missions de recherche sur fixtures, journal durable et vérification sans réseau
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""End-to-end runtime integration on fixed fixtures only, not a Web permission.

No injected provider, URL, transport or DNS adapter. A future real connector
needs its own egress policy, mission binding and operational qualification.
"""
from dataclasses import dataclass
from pathlib import Path
import re

from .contracts import ContractError, digest, encode, snapshot
from .objectives import RESEARCH, RESEARCH_TOOL
from .query_cleanup import clean_query
from .research import AccessFailure, Hit, Page, ResearchCoordinator
from .research_guard import ResearchGuard
from .research_pauses import ResearchPauses
from .runtime import Runtime
from .tools import Policy, Registry, Tool

FIXTURES = {"https://fixture.example/a": "Première page synthétique : information non confirmée.",
            "https://fixture.example/b": "Deuxième page synthétique : observation distincte non confirmée."}
SCENARIOS = {"readable", "partial", "empty", "blocked"}


def fixture_dns(*args):
    # Documentation fixture URL mapped only for the PURE policy check. Never resolved or connected.
    return ["9.9.9.9"]


@dataclass(frozen=True)
class FixtureProvider:
    scenario: str
    provider_id: str = "synthetic-research-provider/1"

    def search(self, query, limit):
        if self.scenario == "blocked":
            raise AccessFailure("ACCESS_DENIED")
        if self.scenario == "empty":
            return []
        return [Hit(url, "Page synthétique") for url in FIXTURES][:limit]


@dataclass(frozen=True)
class FixtureReader:
    scenario: str
    reader_id: str = "synthetic-research-reader/1"

    def read(self, url, policy):
        if url not in FIXTURES:
            raise ContractError("UNKNOWN_RESEARCH_FIXTURE")
        if self.scenario == "partial" and url.endswith("/b"):
            raise AccessFailure("UNAVAILABLE")
        return Page(url=url,status=200,media_type="text/plain",body=FIXTURES[url].encode(),policy_id=policy.policy_id)


@dataclass(frozen=True)
class ResearchModel:
    model_id: str = "deterministic-research-fixture/1"

    def propose(self, request, context):
        objective = context["_core_research"]
        return encode({"version":1,"steps":[{"id":"retrieve","tool":RESEARCH_TOOL,
                      "parameters":{k:objective[k] for k in ("query","required_pages","operation_id")}}]})


@dataclass(frozen=True)
class ResearchFixturePolicy(Policy):
    policy_id: str = "synthetic-research-local-state/1"
    allowed_tools: tuple[str,...] = (RESEARCH_TOOL,)

    def allows(self, tool):
        return (tool is not None and tool.name == RESEARCH_TOOL and tool.name in self.allowed_tools
                and tool.effect == "local_synthetic_state")

    def manifest(self):
        return {"id":self.policy_id,"allowed_tools":sorted(self.allowed_tools),
                "allowed_effect":"local_synthetic_state","scope":"fixed-fixtures-no-network"}


class ResearchVerificationUnavailable(RuntimeError):
    """Missing/busy evidence is not a negative verification verdict."""


class SyntheticResearchBackend:
    def __init__(self, directory, *, scenario="readable"):
        if type(scenario) is not str or scenario not in SCENARIOS:
            raise ContractError("INVALID_RESEARCH_SCENARIO")
        self.directory = str(Path(directory).resolve())
        self.scenario = scenario
        guard = ResearchGuard(Path(directory)/"guard",retain_queries=True)
        self.guard_id = guard.guard_id
        ResearchPauses(Path(directory)/"pauses.sqlite3")

    def manifest(self):
        return {"protocol":"synthetic-research-backend/1","directory":self.directory,
                "guard_id":self.guard_id,"scenario":self.scenario,"fixtures_sha256":digest(FIXTURES)}

    def validate(self, parameters, context):
        if (type(parameters) is not dict or set(parameters)!={"query","required_pages","operation_id"}
                or type(parameters["operation_id"]) is not str or re.fullmatch(r"m-[0-9a-f]{32}",parameters["operation_id"]) is None
                or type(parameters["required_pages"]) is not int or not 1 <= parameters["required_pages"] <= 2):
            raise ContractError("INVALID_RESEARCH_PARAMETERS")
        clean_query(parameters["query"])

    def execute(self, parameters, context):
        self.validate(parameters, context)
        guard = ResearchGuard(Path(self.directory)/"guard",create=False)
        if guard.guard_id != self.guard_id or not guard.retain_queries:
            raise ContractError("RESEARCH_BACKEND_CHANGED")
        pauses_path = Path(self.directory)/"pauses.sqlite3"
        if not pauses_path.is_file():
            raise ContractError("RESEARCH_PAUSES_MISSING")
        coordinator = ResearchCoordinator([FixtureProvider(self.scenario)],FixtureReader(self.scenario),
                     resolver=fixture_dns,guard=guard,pauses=ResearchPauses(pauses_path))
        return coordinator.run(parameters["query"],required_pages=parameters["required_pages"],operation_id=parameters["operation_id"])

    def verify(self, parameters, context, result):
        """Read only: bind exact report to a completed intent, then check fixture evidence."""
        self.validate(parameters, context)
        try:
            result = snapshot(result)
            stamp = result.pop("research_guard")
            if (type(stamp) is not dict or set(stamp)!={"protocol","guard_id","run_id","state"}
                    or stamp["protocol"]!="eidolon-research-guard/1" or stamp["guard_id"]!=self.guard_id
                    or stamp["state"]!="COMPLETED"):
                return False
            try:
                guard = ResearchGuard(Path(self.directory)/"guard",create=False)
                runs = guard.inspect()["runs"]
            except (ContractError, OSError):
                raise ResearchVerificationUnavailable("RESEARCH_VERIFICATION_UNAVAILABLE") from None
            record = next((r for r in runs if r["id"]==stamp["run_id"]),None)
            cleaned = clean_query(parameters["query"])
            if (guard.guard_id != self.guard_id or record is None or record["state"]!="COMPLETED"
                    or record["report_sha256"]!=digest(result)
                    or record["descriptor"]["query_sha256"]!=cleaned.cleaned_sha256
                    or record["descriptor"].get("operation_id")!=parameters["operation_id"]
                    or result["query_cleanup"]!=cleaned.receipt()
                    or result["required_pages"]!=parameters["required_pages"]):
                return False
            readable = [s for s in result["sources"] if s["state"]=="READ"]
            if result["readable_pages"]!=len(readable):
                return False
            if any(s["final_url"] not in FIXTURES or s["text"]!=FIXTURES[s["final_url"]] for s in readable):
                return False
            return True
        except (ContractError, OSError, KeyError, TypeError, ValueError):
            return False

    def tool(self):
        return Tool(RESEARCH_TOOL,digest(self.manifest()),"local_synthetic_state",
                    self.validate,self.execute,self.verify,"synthetic-research-journal-and-fixtures/1")


class ResearchRuntime(Runtime):
    def __init__(self, store, *, scenario="readable", backend=None, model=None, policy=None, **kwargs):
        self.backend = backend or SyntheticResearchBackend(store.directory/"research-fixture",scenario=scenario)
        super().__init__(store, model=model or ResearchModel(),registry=Registry([self.backend.tool()]),
                         policy=policy or ResearchFixturePolicy(), **kwargs)

    def configuration(self):
        return {**super().configuration(),"research_fixture":self.backend.manifest()}

    def create_research(self, query, *, required_pages=1):
        parameters = {"query":query,"required_pages":required_pages}
        self.backend.validate({**parameters,"operation_id":"m-"+"0"*32},{})
        return self.store.create("Rechercher des pages synthétiques : "+query,self.configuration(),
                                 intent={"kind":RESEARCH,**parameters})
