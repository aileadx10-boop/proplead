"""
PropLeads Pro — Crew Definition
================================
Pattern: crewAI-examples/lead-score-flow (@CrewBase + YAML config)

HOW IT WORKS:
- Agent definitions live in config/agents.yaml
- Task definitions live in config/tasks.yaml
- This file just wires them together with @agent and @task decorators
- To change a prompt → edit the YAML, not this file
"""

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

from propleads_pro.tools.attom_tool import AttomTool


@CrewBase
class PropLeadsCrew:
    """PropLeads Pro — motivated seller lead generation crew."""

    agents_config = "config/agents.yaml"
    tasks_config  = "config/tasks.yaml"

    # ── AGENTS ──────────────────────────────────────────────
    # Method name must exactly match the key in agents.yaml

    @agent
    def lead_hunter(self) -> Agent:
        return Agent(
            config=self.agents_config["lead_hunter"],
            tools=[AttomTool(), SerperDevTool()],
            verbose=False,
            allow_delegation=False,
            max_iter=4,
        )

    @agent
    def property_analyzer(self) -> Agent:
        return Agent(
            config=self.agents_config["property_analyzer"],
            tools=[SerperDevTool(), ScrapeWebsiteTool()],
            verbose=False,
            allow_delegation=False,
            max_iter=3,
        )

    @agent
    def motivation_scorer(self) -> Agent:
        return Agent(
            config=self.agents_config["motivation_scorer"],
            tools=[],           # Pure reasoning — no tools = cheapest agent
            verbose=False,
            allow_delegation=False,
            max_iter=2,
        )

    @agent
    def outreach_composer(self) -> Agent:
        return Agent(
            config=self.agents_config["outreach_composer"],
            tools=[],           # Pure generation — no search needed
            verbose=False,
            allow_delegation=False,
            max_iter=2,
        )

    # ── TASKS ────────────────────────────────────────────────
    # Method name must exactly match the key in tasks.yaml

    @task
    def hunt_leads_task(self) -> Task:
        return Task(config=self.tasks_config["hunt_leads_task"])

    @task
    def analyze_properties_task(self) -> Task:
        return Task(config=self.tasks_config["analyze_properties_task"])

    @task
    def score_motivation_task(self) -> Task:
        return Task(config=self.tasks_config["score_motivation_task"])

    @task
    def compose_outreach_task(self) -> Task:
        return Task(config=self.tasks_config["compose_outreach_task"])

    # ── CREW ─────────────────────────────────────────────────

    @crew
    def crew(self) -> Crew:
        """
        Assembles the crew. agents and tasks are auto-collected
        from the @agent and @task decorated methods above.
        """
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=False,
        )
