"""Tokenizador BPE de juguete con una plantilla de chat con herramientas (estilo Gemma), solo para pruebas."""
import json, sys
from tokenizers import Tokenizer, models, trainers, pre_tokenizers, decoders
from transformers import PreTrainedTokenizerFast
text = [l for l in open(sys.argv[1])]  # corpus para el BPE de juguete
tok = Tokenizer(models.BPE(unk_token="<unk>"))
tok.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
tok.decoder = decoders.ByteLevel()
specials = ["<unk>", "<bos>", "<eos>", "<start_of_turn>", "<end_of_turn>", "<tool_call>", "</tool_call>"]
tok.train_from_iterator(text, trainers.BpeTrainer(vocab_size=2000, special_tokens=specials, initial_alphabet=pre_tokenizers.ByteLevel.alphabet()))
t = PreTrainedTokenizerFast(tokenizer_object=tok, bos_token="<bos>", eos_token="<eos>", unk_token="<unk>")
t.chat_template = """{{ bos_token }}{% if tools %}<start_of_turn>system
TOOLS {{ tools | tojson }}<end_of_turn>
{% endif %}{% for m in messages %}{% if m.role == 'assistant' %}<start_of_turn>model
{% if m.tool_calls %}{% for tc in m.tool_calls %}<tool_call>{{ tc.function.name }} {{ tc.function.arguments | tojson }}</tool_call>{% endfor %}{% else %}{{ m.content }}{% endif %}<end_of_turn>
{% elif m.role == 'tool' %}<start_of_turn>tool
{% if m.content is string %}{{ m.content }}{% else %}{% for b in m.content %}{{ b.text }}{% endfor %}{% endif %}<end_of_turn>
{% else %}<start_of_turn>{{ m.role }}
{{ m.content }}<end_of_turn>
{% endif %}{% endfor %}{% if add_generation_prompt %}<start_of_turn>model
{% endif %}"""
t.save_pretrained(sys.argv[2])
