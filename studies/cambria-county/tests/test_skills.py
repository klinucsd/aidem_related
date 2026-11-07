"""Run each Cambria County skill's example code exactly as written in its SKILL.md and check the results.

The example code is what an agent copies, so it is what must keep working when a skill, the GeoServer
layers or the Python packages change. Each test pulls the first ```python block out of a SKILL.md,
runs it in a fresh folder (TEMP_DIR), then checks the files it wrote and the numbers it printed.

Usage (needs network access to sparcal.sdsc.edu; about 1 minute in all):
    pip install geopandas numpy pandas requests rasterio pytest
    pytest -v studies/cambria-county/tests          # or: python studies/cambria-county/tests/test_skills.py

Expected values come from the cascade analysis of USACE's original grids (24 facilities with the team's
hypothetical Franklin Power Ventures,
2,587 buildings wet). The GeoServer grids were reprojected to EPSG:5070, so one building at the flood's
edge comes out wet here too: buildings are checked within a small tolerance.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

SKILLS = Path(__file__).resolve().parents[1] / "skills"


def example(skill: str) -> str:
    """The first ```python block of a skill's SKILL.md."""
    text = (SKILLS / skill / "SKILL.md").read_text()
    match = re.search(r"```python\n(.*?)```", text, re.S)
    assert match, f"{skill}: no python example"
    return match.group(1)


def run(code: str, workdir: Path) -> str:
    """Run code with TEMP_DIR=workdir; return what it printed (fail with its error output)."""
    workdir.mkdir(parents=True, exist_ok=True)
    script = workdir / "example.py"
    script.write_text(code)
    done = subprocess.run([sys.executable, str(script)], cwd=workdir, capture_output=True, text=True,
                          timeout=600, env={**__import__("os").environ, "TEMP_DIR": str(workdir)})
    assert done.returncode == 0, f"example failed:\n{done.stdout[-2000:]}\n{done.stderr[-4000:]}"
    return done.stdout


def number(pattern: str, out: str) -> float:
    match = re.search(pattern, out)
    assert match, f"not printed: {pattern}\n{out[-1500:]}"
    return float(match.group(1).replace(",", ""))


def check_wms(workdir: Path) -> None:
    layer = json.loads((workdir / "cambria_county_flood_depth.wms.json").read_text())
    assert layer["layers"] == "tiger:CambriaCounty_Depth_Max_5070"
    s, w, n, e = layer["bbox"]
    assert s < n and w < e and 40 < s < 41 and -80 < w < -78


# --- the tests ------------------------------------------------------------------------------------
def test_flood_depth(tmp_path):
    out = run(example("cambria-county-flood-depth"), tmp_path)
    assert "WMS layer added" in out
    check_wms(tmp_path)
    # The layer must render: GeoServer returns a PNG for the layer's extent.
    import requests
    r = requests.get("https://sparcal.sdsc.edu/geoserver/tiger/wms", timeout=120, params={
        "service": "WMS", "version": "1.1.1", "request": "GetMap", "layers": "tiger:CambriaCounty_Depth_Max_5070",
        "srs": "EPSG:4326", "bbox": "-79.0759,40.2168,-78.6732,40.4701", "width": 400, "height": 250,
        "format": "image/png", "transparent": "true"})
    assert r.ok and r.content[:4] == b"\x89PNG", r.text[:300]


def test_cikr_schools_with_arrival(tmp_path):
    """The example as written: schools, with arrival time."""
    out = run(example("cambria-county-cikr-impact"), tmp_path)
    check_wms(tmp_path)
    assert number(r"Facilities in the flood grid: (\d+)", out) == 24
    assert number(r"flooded \(any depth\): (\d+)", out) == 6
    flooded = gpd.read_file(tmp_path / "cambria_county_schools_flooded.geojson")
    assert len(flooded) == 6 and flooded.crs.to_epsg() == 4326
    assert {"NAME", "Address", "depth_ft", "severity", "arrival_wet_h"} <= set(flooded.columns)
    assert flooded.arrival_wet_h.notna().all() and flooded.arrival_wet_h.between(-8.84, 10).all()
    assert "hours after the dam failure" in out


def test_cikr_all_types(tmp_path):
    code = example("cambria-county-cikr-impact")
    code = code.replace('filter_type = "Schools"', "filter_type = None").replace('extra = ["arrival_wet_h"]', "extra = []")
    out = run(code, tmp_path)
    assert number(r"Facilities in the flood grid: (\d+)", out) == 169
    flooded = pd.read_csv(tmp_path / "cambria_county_all_cikr_flooded.csv")
    assert len(flooded) == 24
    expected = {"Schools": 6, "Fire Stations": 5, "Law Enforcement": 3, "EMS": 2, "Fire Stations EMS": 1,
                "Intermodal Terminal Facilities": 2, "Hospitals": 1, "Correctional Facilities": 1,
                "Broadcast Communication": 1, "Wastewater Treatment Plants": 1, "Gas-Fired Power Plant": 1}
    assert flooded.Point_Type.value_counts().to_dict() == expected
    assert "Electric Substations" not in set(flooded.Point_Type)   # all CIKR substations stay dry
    deepest = flooded.sort_values("depth_ft").iloc[-1]
    assert deepest.NAME == "DORNICK PT WWTP" and abs(deepest.depth_ft - 35.73) < 0.5
    plant = flooded[flooded.NAME == "Franklin Power Ventures"].iloc[0]   # the team's hypothetical plant
    assert abs(plant.depth_ft - 10.38) < 0.05


def test_cikr_two_types(tmp_path):
    code = example("cambria-county-cikr-impact").replace(
        'filter_type = "Schools"', 'filter_type = ["Hospitals", "Law Enforcement"]')
    out = run(code, tmp_path)
    assert number(r"Facilities in the flood grid: (\d+)", out) == 26
    assert number(r"flooded \(any depth\): (\d+)", out) == 4


def test_nsi(tmp_path):
    out = run(example("cambria-county-nsi-impact"), tmp_path)
    check_wms(tmp_path)
    assert number(r"Buildings in the flood grid: ([\d,]+)", out) == 44_113
    wet = number(r"Flooded buildings: ([\d,]+)", out)
    assert abs(wet - 2_587) <= 5, wet
    assert abs(number(r"Night-time: ([\d,]+)", out) - 5_748) <= 30
    assert abs(number(r"Daytime: +([\d,]+)", out) - 14_373) <= 60
    assert "not damage" in out                       # exposure, never damage
    flooded = gpd.read_file(tmp_path / "cambria_county_nsi_flooded.geojson")
    assert len(flooded) == wet and flooded.crs.to_epsg() == 4326
    summary = pd.read_csv(tmp_path / "cambria_county_nsi_summary.csv")
    assert set(summary.st_damcat) <= {"RES", "COM", "IND", "PUB"}
    assert summary.buildings.sum() == wet


if __name__ == "__main__":
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", "-v", __file__]))
