# Colab start (climb-agent)

## Fresh start (first run today)
```bash
%%bash
set -e
cd /content
rm -rf climb-agent
git clone https://github.com/danielesomensi-cmd/climb-agent.git
cd climb-agent
git config user.name "Daniele Somensi"
git config user.email "daniele.somensi@gmail.com"
git status
git log -n 3 --oneline
```

## Daily start (repo already cloned)
```bash
%%bash
set -e
cd /content/climb-agent
git pull --ff-only
git status
git log -n 3 --oneline
```

## Standard gates (always in this order)
```bash
%%bash
cd /content/climb-agent
python scripts/audit_vocabulary.py
python -m py_compile catalog/engine/resolve_session.py
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/run_baseline_session.py
```
