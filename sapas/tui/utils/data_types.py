from dataclasses import dataclass


@dataclass(frozen=True)
class TestStep:
    """Data representation of an executable test sequence item or condition block parsed from flow files."""
    item_id: str
    runner_index: str
    item_label: str
    flow_item: str
    command: str
    is_condition: bool = False
    condition: str = ""
    row_key: str = ""

    def __post_init__(self) -> None:
        if not self.row_key:
            key = f"if_{self.runner_index}" if self.is_condition else self.item_id
            object.__setattr__(self, "row_key", key)


class FlowNode:
    """Internal AST node for reconstructing hierarchical flow execution trees."""

    def __init__(self, kind: str, cmd: str, item: str, runner_idx: int, condition: str = "") -> None:
        self.kind = kind
        self.cmd = cmd
        self.item = item
        self.runner_idx = runner_idx
        self.condition = condition
        self.children: list["FlowNode"] = []
        self.end_runner_idx = runner_idx


class FlowTreeParser:
    """Reconstructs and formats hierarchical flow trees from flat command pairs."""

    def __init__(self, raw_items: list[list[str]] | list[tuple[str, str]], is_on_fail: bool = False) -> None:
        self.raw_items = raw_items
        self.is_on_fail = is_on_fail
        self.runnable_count = 0

    def parse(self) -> list[TestStep]:
        root_nodes = self._build_ast()
        return self._traverse(root_nodes, prefix="")

    def _build_ast(self) -> list[FlowNode]:
        root_nodes: list[FlowNode] = []
        stack: list[tuple[list[FlowNode], FlowNode | None]] = [(root_nodes, None)]

        for idx, (command, item) in enumerate(self.raw_items):
            cmd = command.strip().lower()
            val = item.strip()
            if cmd == "cycle":
                continue
            if cmd == "if":
                node = FlowNode("if", "if", val, idx, condition=val)
                stack[-1][0].append(node)
                stack.append((node.children, node))
            elif cmd == "end_if":
                if len(stack) > 1:
                    _, parent_node = stack.pop()
                    if parent_node:
                        parent_node.end_runner_idx = idx
            else:
                node = FlowNode("step", cmd, val, idx)
                stack[-1][0].append(node)
        return root_nodes

    def _traverse(self, nodes: list[FlowNode], prefix: str = "") -> list[TestStep]:
        result: list[TestStep] = []
        for node in nodes:
            if node.kind == "if":
                header_label = f"{prefix}IF {node.condition}"
                idx_str = f"F{node.runner_idx:02d}" if self.is_on_fail else f"{node.runner_idx:03d}"
                row_key = f"if_{idx_str}"
                step = TestStep(
                    item_id="",
                    runner_index=idx_str,
                    item_label=header_label,
                    flow_item=node.condition,
                    command="if",
                    is_condition=True,
                    condition=node.condition,
                    row_key=row_key,
                )
                result.append(step)

                # Indent children with tree guide
                result.extend(self._traverse(node.children, prefix + "│  "))

                # Append closing END_IF step
                end_label = f"{prefix}END_IF"
                end_idx_str = f"F{node.end_runner_idx:02d}" if self.is_on_fail else f"{node.end_runner_idx:03d}"
                end_row_key = f"endif_{end_idx_str}"
                end_step = TestStep(
                    item_id="",
                    runner_index=end_idx_str,
                    item_label=end_label,
                    flow_item="end_if",
                    command="end_if",
                    is_condition=True,
                    condition=node.condition,
                    row_key=end_row_key,
                )
                result.append(end_step)
            else:
                step_text = f"{node.cmd} {node.item}".strip() if node.cmd in ("delay", "prompt") else node.item
                display_label = f"{prefix}{step_text}"

                self.runnable_count += 1
                item_id = f"F{self.runnable_count:02d}" if self.is_on_fail else f"{self.runnable_count:03d}"
                idx_str = f"F{node.runner_idx:02d}" if self.is_on_fail else f"{node.runner_idx:03d}"
                step_obj = TestStep(
                    item_id=item_id,
                    runner_index=idx_str,
                    item_label=display_label,
                    flow_item=node.item,
                    command=node.cmd,
                    is_condition=False,
                    condition="",
                    row_key=item_id,
                )
                result.append(step_obj)
        return result


def parse_flow_tree(raw_items: list[list[str]] | list[tuple[str, str]], is_on_fail: bool = False) -> list[TestStep]:
    """Parses flat flow item pairs into hierarchical TestStep objects with tree connectors."""
    return FlowTreeParser(raw_items, is_on_fail=is_on_fail).parse()
