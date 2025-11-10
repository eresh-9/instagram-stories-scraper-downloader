thonimport argparse
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

# Ensure local imports work when running as a script
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

try:
    from extractors.story_parser import parse_stories
    from outputs.json_exporter import export_stories_to_json
except ImportError as exc:  # pragma: no cover - defensive
    raise SystemExit(f"Failed to import project modules: {exc}") from exc

def configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

def load_config() -> Dict[str, Any]:
    """
    Load configuration from settings.json if present, otherwise
    fall back to settings.example.json. All paths are resolved
    relative to the project root.
    """
    config_dir = os.path.join(CURRENT_DIR, "config")
    primary_path = os.path.join(config_dir, "settings.json")
    example_path = os.path.join(config_dir, "settings.example.json")

    path_to_use = None
    if os.path.exists(primary_path):
        path_to_use = primary_path
    elif os.path.exists(example_path):
        path_to_use = example_path

    if not path_to_use:
        logging.warning("No configuration file found; using internal defaults.")
        return {}

    try:
        with open(path_to_use, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            raise ValueError("Config root must be a JSON object")
        return raw
    except Exception as exc:  # pragma: no cover - defensive
        logging.error("Failed to load config from %s: %s", path_to_use, exc)
        return {}

def resolve_path(value: Optional[str], default_relative: str) -> str:
    if value and value.strip():
        path = value
    else:
        path = default_relative
    if not os.path.isabs(path):
        path = os.path.join(PROJECT_ROOT, path)
    return path

def parse_args(config: Dict[str, Any]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Instagram Stories Scraper Downloader - JSON normalizer"
    )
    parser.add_argument(
        "-i",
        "--input",
        dest="input_path",
        help="Path to raw stories JSON file "
             "(default: config default_input_path or data/sample_input.json)",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output_path",
        help="Path for normalized output JSON "
             "(default: config default_output_path or data/sample_output.json)",
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        default=config.get("log_level", "INFO"),
        help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of stories processed",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output (indentation)",
    )
    return parser.parse_args()

def load_raw_input(input_path: str) -> Any:
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logging.info("Loaded raw input from %s", input_path)
        return data
    except json.JSONDecodeError as exc:
        logging.error("Invalid JSON in %s: %s", input_path, exc)
        raise
    except Exception as exc:  # pragma: no cover - defensive
        logging.error("Failed to read %s: %s", input_path, exc)
        raise

def main() -> None:
    config = load_config()
    args = parse_args(config)
    configure_logging(args.log_level)

    raw_input_path = resolve_path(
        args.input_path,
        config.get("default_input_path", os.path.join("data", "sample_input.json")),
    )
    output_path = resolve_path(
        args.output_path,
        config.get("default_output_path", os.path.join("data", "sample_output.json")),
    )

    logging.debug("Using input path: %s", raw_input_path)
    logging.debug("Using output path: %s", output_path)

    try:
        raw = load_raw_input(raw_input_path)
    except Exception as exc:
        logging.critical("Aborting due to input load failure: %s", exc)
        raise SystemExit(1) from exc

    try:
        stories: List[Dict[str, Any]] = parse_stories(raw)
    except Exception as exc:
        logging.critical("Failed to parse stories: %s", exc)
        raise SystemExit(2) from exc

    if args.limit is not None and args.limit >= 0:
        stories = stories[: args.limit]
        logging.info("Limiting processed stories to %d entries", len(stories))

    try:
        export_stories_to_json(stories, output_path, pretty=args.pretty)
    except Exception as exc:
        logging.critical("Failed to export stories: %s", exc)
        raise SystemExit(3) from exc

    logging.info("Successfully processed %d stories", len(stories))
    logging.info("Normalized output written to %s", output_path)

if __name__ == "__main__":
    main()