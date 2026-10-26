"""Basic-block and control-flow-graph construction for generated TAC."""
from dataclasses import dataclass


@dataclass
class BasicBlock:
    number: int
    start: int
    end: int
    code: list
    successors: list


def build_cfg(code):
    """Return basic blocks and successor block numbers for a TAC listing.

    Leaders are the first instruction, every label, every jump target, and the
    instruction immediately following a conditional or unconditional jump.
    """
    if not code:
        return []

    labels = {ins.res: i for i, ins in enumerate(code) if ins.op == "label"}
    leaders = {0}
    for i, ins in enumerate(code):
        if ins.op == "label":
            leaders.add(i)
        if ins.is_jump:
            if ins.res in labels:
                leaders.add(labels[ins.res])
            if i + 1 < len(code):
                leaders.add(i + 1)

    starts = sorted(leaders)
    index_to_block = {}
    blocks = []
    for number, start in enumerate(starts):
        end = starts[number + 1] if number + 1 < len(starts) else len(code)
        block = BasicBlock(number, start, end, code[start:end], [])
        blocks.append(block)
        for index in range(start, end):
            index_to_block[index] = number

    label_to_block = {name: index_to_block[index] for name, index in labels.items()}
    for block in blocks:
        last_index = block.end - 1
        last = code[last_index]
        successors = []
        if last.op == "goto":
            target = label_to_block.get(last.res)
            if target is not None:
                successors.append(target)
        elif last.is_cond_jump:
            target = label_to_block.get(last.res)
            if target is not None:
                successors.append(target)
            if block.end < len(code):
                successors.append(index_to_block[block.end])
        elif block.end < len(code):
            successors.append(index_to_block[block.end])
        block.successors = list(dict.fromkeys(successors))
    return blocks
