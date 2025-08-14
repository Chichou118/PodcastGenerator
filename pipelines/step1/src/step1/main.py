import argparse
from pathlib import Path
from podcast_generator.config import load_yaml
from podcast_generator.logging import setup_logger

def run(config_path: str):
    cfg = load_yaml(config_path)
    log = setup_logger("step1")
    out_dir = Path(cfg.paths["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    # TODO: implement fetch -> rank -> require_full_text -> write card
    log.info("Step1 completed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/step1.yaml")
    args = parser.parse_args()
    run(args.config)