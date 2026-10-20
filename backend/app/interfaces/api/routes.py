"""REST uç noktaları (blueprint'ler)."""
from flask import Blueprint, Response, jsonify, request

from app.application.reports import RunSheetConditions
from app.domain.design.model_matrix import term_names
from app.domain.evaluation.desirability import Goals
from app.domain.process.model import PARAMETER_GROUPS, RESPONSES, ProcessSettings
from app.domain.process.scenarios import SCENARIOS
from app.domain.shared.factors import FACTORS
from app.interfaces.api.requests import body, container, parse_goals, parse_overrides, parse_settings

meta_bp = Blueprint("meta", __name__)
literature_bp = Blueprint("literature", __name__)
simulation_bp = Blueprint("simulation", __name__)
designs_bp = Blueprint("designs", __name__)
evaluation_bp = Blueprint("evaluation", __name__)
reports_bp = Blueprint("reports", __name__)


@meta_bp.get("/meta")
def meta():
    params = container().simulation.parameters().to_dict()
    return jsonify({
        "factors": [f.to_dict() for f in FACTORS],
        "responses": list(RESPONSES),
        "model_terms": term_names(),
        "parameters": params,
        "parameter_groups": PARAMETER_GROUPS,
        "scenarios": [s.to_dict() for s in SCENARIOS.values()],
        "default_settings": {"n_applications": ProcessSettings.n_applications,
                             "target_moisture": ProcessSettings.target_moisture},
        "default_goals": Goals().to_dict(),
    })


@literature_bp.get("/literature")
def literature():
    return jsonify(container().literature.summary())


@simulation_bp.post("/simulate")
def simulate():
    data = body()
    return jsonify(container().simulation.simulate(
        data.get("point") or {}, parse_settings(data), parse_goals(data), parse_overrides(data)))


@simulation_bp.post("/simulate/sweep")
def sweep():
    data = body()
    return jsonify(container().simulation.sweep(
        data.get("point") or {}, data.get("factor", "h2o2_time"), parse_settings(data), parse_overrides(data)))


@simulation_bp.post("/simulate/optimum")
def optimum():
    data = body()
    return jsonify(container().simulation.literature_optimum(parse_settings(data), parse_goals(data), parse_overrides(data)))


@designs_bp.get("/designs")
def designs():
    return jsonify(container().designs.catalog())


@designs_bp.get("/designs/<key>")
def design_detail(key):
    svc = container().designs
    seed = request.args.get("seed", default=1, type=int)
    return jsonify({**svc.run_table(key, seed), "criteria": svc.criteria(key)})


@designs_bp.get("/designs/<key>/csv")
def design_csv(key):
    seed = request.args.get("seed", default=1, type=int)
    csv_text = container().designs.run_table_csv(key, seed)
    return Response(csv_text, mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=deney_tablosu_{key}.csv"})


@evaluation_bp.post("/evaluate")
def evaluate():
    data = body()
    return jsonify(container().evaluation.compare(
        design_keys=list(data.get("designs") or []),
        scenario_keys=list(data.get("scenarios") or ["base"]),
        settings=parse_settings(data),
        goals=parse_goals(data),
        overrides=parse_overrides(data),
        n_reps=int(data.get("n_reps", 200)),
        log_transform=bool(data.get("log_transform", True)),
        seed=int(data.get("seed", 0)),
    ))


def _pdf(content: bytes, filename: str) -> Response:
    return Response(content, mimetype="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@designs_bp.get("/designs/<key>/pdf")
def design_pdf(key):
    seed = request.args.get("seed", default=1, type=int)
    conditions = RunSheetConditions(
        n_applications=request.args.get("n_applications", type=int),
        target_moisture=request.args.get("target_moisture", type=float),
        pressure_mode=request.args.get("pressure_mode") or None,
    )
    return _pdf(container().reports.run_table_pdf(key, seed, conditions), f"deney_foyu_{key}.pdf")


@reports_bp.post("/reports/comparison")
def comparison_report():
    data = body()
    return _pdf(container().reports.comparison_pdf(data.get("result") or {}), "desen_karsilastirma_raporu.pdf")


@reports_bp.post("/reports/simulation")
def simulation_report():
    data = body()
    return _pdf(container().reports.simulation_pdf(
        data.get("point") or {}, parse_settings(data), parse_goals(data), parse_overrides(data)),
        "simulasyon_raporu.pdf")


BLUEPRINTS = (meta_bp, literature_bp, simulation_bp, designs_bp, evaluation_bp, reports_bp)
