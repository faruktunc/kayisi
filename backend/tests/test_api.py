import pytest

from app import create_app


@pytest.fixture(scope="module")
def client():
    return create_app({"TESTING": True}).test_client()


def test_meta(client):
    data = client.get("/api/meta").get_json()
    assert len(data["factors"]) == 6
    assert data["default_settings"]["n_applications"] == 1


def test_literature_calibration(client):
    data = client.get("/api/literature").get_json()
    assert data["fit"]["n_obs"] == 63
    assert data["fit"]["r2_so2"] > 0.8


def test_simulate_and_sweep(client):
    r = client.post("/api/simulate", json={"point": {"so2_initial": 3500}, "settings": {"n_applications": 2}}).get_json()
    assert r["so2_final"] > 0 and r["drying_time"] > 0
    s = client.post("/api/simulate/sweep", json={"factor": "dry_temp"}).get_json()
    assert len(s["x"]) == len(s["responses"]["drying_time"])


def test_invalid_input_returns_400(client):
    assert client.post("/api/simulate", json={"settings": {"n_applications": 9}}).status_code == 400
    assert client.post("/api/simulate", json={"overrides": {"nope": 1}}).status_code == 400
    assert client.get("/api/designs/yok").status_code == 400


def test_design_table_and_csv(client):
    d = client.get("/api/designs/bbd").get_json()
    assert len(d["rows"]) == 54
    csv = client.get("/api/designs/bbd/csv")
    assert csv.status_code == 200 and "Deney sırası" in csv.get_data(as_text=True)


def test_evaluate(client):
    r = client.post("/api/evaluate", json={"designs": ["ccd_half", "d_opt_36"], "scenarios": ["base", "high_noise"],
                                           "n_reps": 20}).get_json()
    assert len(r["ranking"]) == 2
    assert r["recommendation"]["design"] in ("ccd_half", "d_opt_36")
    assert len(r["scenarios"]) == 2


def test_pdf_exports(client):
    foy = client.get("/api/designs/d_opt_36/pdf")
    assert foy.status_code == 200 and foy.data.startswith(b"%PDF")
    sim = client.post("/api/reports/simulation", json={"point": {"so2_initial": 4000}})
    assert sim.status_code == 200 and sim.data.startswith(b"%PDF")
    ev = client.post("/api/evaluate", json={"designs": ["bbd", "d_opt_30"], "n_reps": 20}).get_json()
    cmp = client.post("/api/reports/comparison", json={"result": ev})
    assert cmp.status_code == 200 and cmp.data.startswith(b"%PDF")
    assert client.post("/api/reports/comparison", json={"result": {}}).status_code == 400


def test_run_sheet_conditions(client):
    assert client.get("/api/designs/ccd_half/pdf").status_code == 200
    ok = client.get("/api/designs/ccd_half/pdf?n_applications=2&target_moisture=22&pressure_mode=absolute")
    assert ok.status_code == 200 and ok.data.startswith(b"%PDF")
    assert client.get("/api/designs/ccd_half/pdf?pressure_mode=x").status_code == 400
    assert client.get("/api/designs/ccd_half/pdf?n_applications=9").status_code == 400
