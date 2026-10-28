"""Build a complete, shareable CampusFix project archive."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    destination = ROOT / "CampusFix_Complete_Project.zip"
    files = []
    for folder in ("app", "src", "tests", "data", "models", "reports"):
        for path in (ROOT / folder).rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            if "__pycache__" in relative.parts or path.suffix == ".pyc":
                continue
            if "uploads" in relative.parts and path.name != ".gitkeep":
                continue
            if path.name.startswith(".env") or path.suffix in (".db", ".sqlite", ".sqlite3"):
                continue
            files.append(path)
    for name in (".gitignore", "config.py", "run.py", "seed.py", "README.md", "requirements.txt", "requirements-offline.txt", "CampusFix_ML_Report_Results.zip"):
        files.append(ROOT / name)
    # Compatible combined installation for the Python version used in the run.
    ml_names = {line.split("==")[0] for line in (ROOT / "requirements-offline.txt").read_text().splitlines() if "==" in line}
    web = [line for line in (ROOT / "requirements.txt").read_text().splitlines() if line and line.split("==")[0] not in ml_names]
    offline = (ROOT / "requirements-offline.txt").read_text()
    instructions = """# CampusFix complete project

Includes the application, existing synthetic dataset, offline ML training and
evaluation scripts, actual experimental results, selected offline model
binaries, tests, and the report-only ZIP.

From this extracted CampusFix directory, using Python 3.14:

```powershell
python -m venv venv
.\\venv\\Scripts\\python.exe -m pip install -r requirements-bundle.txt
.\\venv\\Scripts\\python.exe -m src.verify_offline
.\\venv\\Scripts\\python.exe -m src.train
.\\venv\\Scripts\\python.exe -m src.evaluate
.\\venv\\Scripts\\python.exe run.py
```

Flask creates database tables on first run. Register an account or use the
existing demo login flow. The local database and uploaded attachments are
excluded. Offline pipelines remain in models/offline_evaluation/; the website
keeps its original prediction behavior.

Read reports/offline_evaluation/REPORT_RESULTS.md for the actual results and
limitations. All dataset records are synthetic. Emergency recall is zero on
this grouped held-out set; these results do not establish deployment readiness.

Excluded: virtual environment, caches, credentials, local database, uploaded
attachments, server logs, and superseded artifacts in previous_ml_attempt/.
Original dependency files are retained. requirements-bundle.txt combines the
web dependencies with the exact ML dependency pins used for this experiment.
"""
    hashes = {}
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            relative = path.relative_to(ROOT).as_posix()
            archive.write(path, "CampusFix/" + relative)
            hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        archive.writestr("CampusFix/instance/", "")
        archive.writestr("CampusFix/START_HERE.md", instructions)
        archive.writestr("CampusFix/requirements-bundle.txt", "\n".join(web) + "\n" + offline)
        archive.writestr("CampusFix/PACKAGE_SHA256.json", json.dumps(hashes, indent=2))
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        assert "CampusFix/models/offline_evaluation/category_model.pkl" in archive.namelist()
        assert "CampusFix/data/complaints.csv" in archive.namelist()
        print(f"Created {destination.name}: {len(archive.namelist())} entries, {destination.stat().st_size:,} bytes. ZIP integrity verified.")


if __name__ == "__main__":
    main()
