"""Bağımlılıkların tek yerde kurulduğu basit servis kabı."""
from dataclasses import dataclass
from pathlib import Path

from app.application.reports import ReportService
from app.application.services import DesignService, EvaluationService, LiteratureService, SimulationService
from app.infrastructure.literature_repository import JsonLiteratureRepository


@dataclass
class Container:
    literature: LiteratureService
    simulation: SimulationService
    designs: DesignService
    evaluation: EvaluationService
    reports: ReportService

    @classmethod
    def build(cls, literature_path: Path) -> "Container":
        literature = LiteratureService(JsonLiteratureRepository(literature_path))
        simulation = SimulationService(literature)
        designs = DesignService()
        return cls(literature, simulation, designs, EvaluationService(simulation, designs),
                   ReportService(simulation, designs, literature))
