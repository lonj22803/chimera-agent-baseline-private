from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import StructuredTool

from Ablation_study.harness.catalogo import (
    EXPECTED_IDS,
    EXPECTED_STRUCTURAL_IDS,
    load_catalog,
)
from version_final_reto.common.roster import GUIDELINE_TOOL, SECTION_BY_TOOL
from version_final_reto.task_1.agent.graph import create_conference_graph


class _Mute(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "mute"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="{}"))])


def _fake_tools() -> list[StructuredTool]:
    def noop(query: str = "") -> str:
        """Herramienta muda usada solo para compilar el grafo."""
        return "{}"

    names = [*SECTION_BY_TOOL, GUIDELINE_TOOL]
    return [
        StructuredTool.from_function(
            noop,
            name=name,
            description=f"Fake {name} used only while compiling the graph.",
        )
        for name in names
    ]


def test_catalog_has_every_preregistered_id_and_covers_the_compiled_graph() -> None:
    catalog = load_catalog()
    assert {item.id for item in catalog.intervenciones} == EXPECTED_IDS
    assert {item.id for item in catalog.estructural} == EXPECTED_STRUCTURAL_IDS
    assert all(item.por_que for item in catalog.estructural)

    graph = create_conference_graph(_fake_tools(), _Mute(), None, None, None)
    compiled_nodes = set(graph.get_graph().nodes)

    assert compiled_nodes <= set(catalog.node_owners), (
        "Nodos de la V4 sin catalogar: "
        f"{sorted(compiled_nodes - set(catalog.node_owners))}"
    )
