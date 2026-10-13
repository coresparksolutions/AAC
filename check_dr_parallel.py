import os
import csv
import time
from pathlib import Path

import requests

DEFAULT_INPUT_FILE = "links.txt"
DEFAULT_OUTPUT_DIR = "results"
DR_VERSION = "dr3"
RATE_LIMIT_DELAY = 1.1


def get_runtime_config():
    """Return the runtime configuration used by the CLI or dashboard."""
    api_keys = [k.strip() for k in os.environ.get("AHREFS_API_KEYS", "").split(",") if k.strip()]
    shard_index = int(os.environ.get("SHARD_INDEX", "0"))
    shard_count = int(os.environ.get("SHARD_COUNT", "1"))
    input_file = os.environ.get("AAC_INPUT_FILE", DEFAULT_INPUT_FILE)
    output_dir = os.environ.get("AAC_OUTPUT_DIR", DEFAULT_OUTPUT_DIR)
    return {
        "api_keys": api_keys,
        "api_key": api_keys[shard_index] if shard_index < len(api_keys) else None,
        "shard_index": shard_index,
        "shard_count": shard_count,
        "input_file": input_file,
        "output_dir": output_dir,
        "dr_version": os.environ.get("AHREFS_DR_VERSION", DR_VERSION),
        "rate_limit_delay": float(os.environ.get("AAC_RATE_LIMIT_DELAY", RATE_LIMIT_DELAY)),
    }


def load_processed(output_file):
    """Return the set of targets already saved in this shard's CSV."""
    done = set()
    output_path = Path(output_file)
    if output_path.exists():
        with output_path.open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if row:
                    done.add(row[0])
    return done


def check_dr(target, api_key=None, dr_version=DR_VERSION):
    """Check a target using the Ahrefs free public API."""
    if not api_key:
        cfg = get_runtime_config()
        api_key = cfg["api_key"]
        dr_version = cfg["dr_version"]

    if not api_key:
        raise ValueError("No AHREFS_API_KEYS configured for this shard.")

    url = "https://api.ahrefs.com/v3/public/domain-rating-free"
    params = {"target": target, "version": dr_version, "output": "json"}
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=20)
        if response.status_code == 200:
            dr = response.json().get("domain_rating", {}).get("domain_rating")
            return (target, dr, "")
        if response.status_code == 429:
            print("Rate limited — backing off 65s...")
            time.sleep(65)
            response = requests.get(url, params=params, headers=headers, timeout=20)
            if response.status_code == 200:
                dr = response.json().get("domain_rating", {}).get("domain_rating")
                return (target, dr, "")
        return (target, "", f"HTTP {response.status_code}")
    except Exception as exc:  # pragma: no cover - CLI-friendly fallback
        return (target, "", str(exc))


def load_targets(input_file):
    with open(input_file, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def process_targets(targets, api_key, shard_index=0, shard_count=1, output_dir=DEFAULT_OUTPUT_DIR, rate_limit_delay=RATE_LIMIT_DELAY, dr_version=DR_VERSION):
    """Process the targets assigned to this shard and append results to CSV."""
    if not api_key:
        raise ValueError("API key is required to process targets.")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    output_file = output_path / f"shard_{shard_index}.csv"

    my_targets = [target for idx, target in enumerate(targets) if idx % shard_count == shard_index]
    done = load_processed(output_file)
    todo = [target for target in my_targets if target not in done]

    print(f"Shard {shard_index}/{shard_count - 1}: assigned={len(my_targets)} done={len(done)} todo={len(todo)}")
    if not todo:
        print("Nothing to do.")
        return []

    file_exists = output_file.exists()
    with output_file.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["target", "domain_rating", "error"])
        results = []
        for i, target in enumerate(todo, 1):
            row = check_dr(target, api_key=api_key, dr_version=dr_version)
            writer.writerow(row)
            results.append(row)
            f.flush()
            os.fsync(f.fileno())
            if i % 100 == 0:
                print(f"Shard {shard_index}: {i}/{len(todo)}")
            time.sleep(rate_limit_delay)
    return results


def main():
    cfg = get_runtime_config()
    api_keys = cfg["api_keys"]
    shard_index = cfg["shard_index"]
    shard_count = cfg["shard_count"]

    if shard_index >= len(api_keys):
        print(f"Shard {shard_index} has no assigned API key. Exiting.")
        raise SystemExit(0)

    api_key = api_keys[shard_index]
    input_file = cfg["input_file"]
    output_dir = cfg["output_dir"]
    dr_version = cfg["dr_version"]
    rate_limit_delay = cfg["rate_limit_delay"]

    targets = load_targets(input_file)
    process_targets(
        targets=targets,
        api_key=api_key,
        shard_index=shard_index,
        shard_count=shard_count,
        output_dir=output_dir,
        rate_limit_delay=rate_limit_delay,
        dr_version=dr_version,
    )


if __name__ == "__main__":
    main()
