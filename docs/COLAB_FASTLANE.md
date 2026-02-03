# Colab fastlane

## Uso rapido

```bash
python scripts/colab_fastlane.py \
  --branch chore/colab-fastlane \
  --patch /path/to/changes.patch \
  --commit_msg "Apply patch" \
  --run "pytest -q"
```

> Nota: Codex NON pusha; push sempre da Colab con fastlane.

> smoke test fastlane
