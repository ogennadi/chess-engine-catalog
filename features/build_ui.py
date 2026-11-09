"""Build features/feature-selector.html from taxonomy.json + summary.json.

Run extract_readme_features.py first to refresh summary.json.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    data = json.loads((HERE / "taxonomy.json").read_text(encoding="utf8"))
    summary_path = HERE / "summary.json"
    if summary_path.exists():
        data["stats"] = json.loads(summary_path.read_text(encoding="utf8"))
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = (HERE / "ui.template.html").read_text(encoding="utf8").replace("__DATA__", payload)
    out = HERE / "feature-selector.html"
    out.write_text(html, encoding="utf8")
    print(f"wrote {out} ({len(html) // 1024} KB)")


if __name__ == "__main__":
    main()
