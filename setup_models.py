"""Download model data only; no remote Python execution, no API credentials."""
from huggingface_hub import snapshot_download
from pipeline import ROOT
snapshot_download('BAAI/bge-small-zh-v1.5',revision='7999e1d3359715c523056ef9478215996d62a620',local_dir=str(ROOT/'models/bge-small-zh-v1.5'),allow_patterns=['config.json','model.safetensors','tokenizer.json','tokenizer_config.json','special_tokens_map.json','vocab.txt'])
snapshot_download('mlx-community/Qwen2.5-7B-Instruct-4bit',revision='c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed',local_dir=str(ROOT/'models/Qwen2.5-7B-Instruct-4bit'),allow_patterns=['*.json','*.safetensors','*.txt'])
