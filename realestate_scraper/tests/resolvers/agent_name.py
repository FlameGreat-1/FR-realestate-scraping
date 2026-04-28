from __future__ import annotations

from scraper.extractors.pipeline_extract import parse_page
from scraper.models import DomainJob
from scraper.resolvers.agent_name import AgentNameResolver

RESOLVER = AgentNameResolver()


def test_agent_name_from_dom():
    html = '<html><body><span class="agent-name">Marie Dupont</span></body></html>'
    ctx = parse_page("https://x.com/x", html)
    assert RESOLVER.resolve(ctx).value == "Marie Dupont"


def test_agent_name_falls_back_to_csv():
    job = DomainJob(
        domain="x.com",
        url="https://x.com",
        agent_name="Patrimoine Rh",
    )
    ctx = parse_page("https://x.com/listing/12345", "<html></html>", domain_job=job)
    assert RESOLVER.resolve(ctx).value == "Patrimoine Rh"


def test_agent_name_empty_when_no_signal():
    ctx = parse_page("https://x.com/x", "<html></html>")
    assert RESOLVER.resolve(ctx).value == ""
