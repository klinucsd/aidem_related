# AidEM related

Materials shared with the AidEM team, organised by study.

```
studies/
  <study>/
    README.md        what the study is, how its materials were made and tested
    skills/          agent skills for the study, one folder per skill (SKILL.md)
    tests/           tests that run each skill's example code and check its results
```

## Studies

| Study | What | Contents |
|---|---|---|
| [cambria-county](studies/cambria-county) | Cambria County South Fork Dam Breach Scenario: USACE's simulated dam failure near Johnstown, PA (December demo data; not a real event) | Skills: flood depth map, critical facility impact, building and population impact (NSI 2026) |

The skills read the study data from the SDSC GeoServer (`https://sparcal.sdsc.edu/geoserver/tiger`),
so no data needs to be installed.
