"""Modelo Llama diminuto y aleatorio sobre el tokenizador de juguete, para la prueba de humo."""
import json
import sys

from transformers import AutoTokenizer, LlamaConfig, LlamaForCausalLM

tok = AutoTokenizer.from_pretrained(sys.argv[1])
eos = tok.convert_tokens_to_ids("<end_of_turn>")
cfg = LlamaConfig(vocab_size=len(tok), hidden_size=64, intermediate_size=128, num_hidden_layers=2,
                  num_attention_heads=4, num_key_value_heads=2, max_position_embeddings=8192,
                  eos_token_id=eos, bos_token_id=tok.bos_token_id)
LlamaForCausalLM(cfg).save_pretrained(sys.argv[2])
tok.save_pretrained(sys.argv[2])
json.dump({"eos_token_id": eos}, open(f"{sys.argv[2]}/generation_config.json", "w"))
