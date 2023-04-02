import json
import os
import signal
import sys
from pathlib import Path

import huggingface_hub
import transformers
from loguru import logger


def terminate(signum, frame):
    print("Terminating...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, terminate)
    model_id = os.getenv("MODEL_ID")
    snapshot_dir = Path(huggingface_hub.snapshot_download(model_id))
    for file in snapshot_dir.rglob("*.json"):
        text = file.read_text()
        text = text.replace("LLaMA", "Llama")
        file.write_text(text)

    hf_config = transformers.AutoConfig.from_pretrained(str(snapshot_dir))
    if hasattr(hf_config, "vocab_size"):
        logger.info(f"Vocab size in config: {hf_config.vocab_size}")
        tokenizer_config_path = snapshot_dir / "tokenizer_config.json"
        if tokenizer_config_path.exists():
            logger.info(f"found tokenizer config: {tokenizer_config_path}")
            tokenizer_config = json.loads(tokenizer_config_path.read_text())
            if "vocab_size" not in tokenizer_config:
                tokenizer_config["vocab_size"] = hf_config.vocab_size
                tokenizer_config_path.write_text(json.dumps(tokenizer_config))
