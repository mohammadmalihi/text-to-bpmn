"""
Utilities to convert natural language descriptions into a lightweight BPMN diagram.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple
from xml.sax.saxutils import escape


def convert_text_to_bpmn(user_text: str) -> str:
    """
    Convert a plain language description into a BPMN XML diagram string.
    """
    steps = _extract_steps(user_text)
    if not steps:
        raise ValueError(
            "امکان ساخت نمودار وجود ندارد. لطفاً توضیح را با جملات یا مراحل مشخص وارد کنید."
        )

    process_id = "Process_1"
    start_id = "StartEvent_1"
    end_id = "EndEvent_1"

    # Try to detect a simple branching scenario from the text (اگر ... باشد ... اما اگر ...)
    branch = _detect_branch(user_text)
    multi_branch = None if branch else _detect_multi_branch(user_text)

    if branch or multi_branch:
        # Build a diagram with an exclusive gateway split and join
        process_elements: List[str] = [
            f'<bpmn:startEvent id="{start_id}" name="شروع"/>']

        node_types: Dict[str, str] = {
            start_id: "start",
            end_id: "end",
        }
        node_columns: Dict[str, int] = {start_id: 0}
        node_rows: Dict[str, int] = {start_id: 0}
        label_lines_by_id: Dict[str, int] = {}
        nodes_order: List[str] = [start_id]
        edges: List[Tuple[str, str, str]] = []

        # Steps before the decision (use text before first 'اگر')
        pre_text = user_text.split("اگر", 1)[0]
        pre_steps = _extract_steps(pre_text)

        pre_task_ids: List[str] = []
        for index, step in enumerate(pre_steps):
            label = _format_label_with_role(step)
            node_id = f"Activity_{index+1}"
            pre_task_ids.append(node_id)
            nodes_order.append(node_id)
            node_types[node_id] = "task"
            node_columns[node_id] = index + 1
            node_rows[node_id] = 0
            label_lines_by_id[node_id] = label.count("\n") + 1
            process_elements.append(
                f'<bpmn:task id="{node_id}" name="{escape(label)}"/>')

        # Decision gateway
        split_id = "Gateway_Split_1"
        question = (branch or {}).get("question") or "تصمیم‌گیری"
        process_elements.append(
            f'<bpmn:exclusiveGateway id="{split_id}" name="{escape(question)}"/>'
        )
        node_types[split_id] = "gateway"
        node_columns[split_id] = (node_columns.get(
            pre_task_ids[-1], 0) + 1) if pre_task_ids else 1
        node_rows[split_id] = 0
        nodes_order.append(split_id)

        # Build branches
        branch_start_ids: List[str] = []
        branch_end_ids: List[str] = []
        branch_internal_edges: List[Tuple[str, str]] = []
        branch_levels: Dict[str, int] = {}
        branch_rows: Dict[str, int] = {}
        if branch:
            # yes/no branches
            yes_label = _format_label_with_role(branch["yes_action"])
            yes_id = "Activity_Yes_1"
            process_elements.append(
                f'<bpmn:task id="{yes_id}" name="{escape(yes_label)}"/>')
            node_types[yes_id] = "task"
            node_columns[yes_id] = node_columns[split_id] + 1
            node_rows[yes_id] = 0
            nodes_order.append(yes_id)
            label_lines_by_id[yes_id] = yes_label.count("\n") + 1
            branch_start_ids.append(yes_id)
            branch_end_ids.append(yes_id)
            branch_levels[yes_id] = node_columns[yes_id]
            branch_rows[yes_id] = node_rows[yes_id]

            no_label = _format_label_with_role(branch["no_action"])
            no_id = "Activity_No_1"
            process_elements.append(
                f'<bpmn:task id="{no_id}" name="{escape(no_label)}"/>')
            node_types[no_id] = "task"
            node_columns[no_id] = node_columns[split_id] + 1
            node_rows[no_id] = 1
            nodes_order.append(no_id)
            label_lines_by_id[no_id] = no_label.count("\n") + 1
            branch_start_ids.append(no_id)
            branch_end_ids.append(no_id)
            branch_levels[no_id] = node_columns[no_id]
            branch_rows[no_id] = node_rows[no_id]

            # Optional follow-up on the "no" path
            if branch.get("after_no_action"):
                follow_label = _format_label_with_role(
                    branch["after_no_action"])
                follow_id = "Activity_No_2"
                process_elements.append(
                    f'<bpmn:task id="{follow_id}" name="{escape(follow_label)}"/>')
                node_types[follow_id] = "task"
                node_columns[follow_id] = node_columns[no_id] + 1
                node_rows[follow_id] = 1
                nodes_order.append(follow_id)
                label_lines_by_id[follow_id] = follow_label.count("\n") + 1
                # Update end node for 'no' branch (do not change its start)
                branch_end_ids[-1] = follow_id
                branch_levels[follow_id] = node_columns[follow_id]
                branch_rows[follow_id] = node_rows[follow_id]
                # Connect no -> follow
                branch_internal_edges.append((no_id, follow_id))
        else:
            # Multi-branch detected
            for idx, action in enumerate(multi_branch["branches"]):
                label = _format_label_with_role(action)
                node_id = f"Activity_B_{idx+1}"
                process_elements.append(
                    f'<bpmn:task id="{node_id}" name="{escape(label)}"/>')
                node_types[node_id] = "task"
                node_columns[node_id] = node_columns[split_id] + 1
                node_rows[node_id] = idx
                nodes_order.append(node_id)
                label_lines_by_id[node_id] = label.count("\n") + 1
                branch_start_ids.append(node_id)
                branch_end_ids.append(node_id)
                branch_levels[node_id] = node_columns[node_id]
                branch_rows[node_id] = node_rows[node_id]

        # Join gateway
        join_id = "Gateway_Join_1"
        process_elements.append(
            f'<bpmn:exclusiveGateway id="{join_id}" name=""/>')
        node_types[join_id] = "gateway"
        # place join below the deepest branch level
        max_level = max(branch_levels.values()) if branch_end_ids else node_columns.get(
            split_id, 0)
        node_columns[join_id] = max_level + 1
        node_rows[join_id] = 0
        nodes_order.append(join_id)

        # End
        process_elements.append(f'<bpmn:endEvent id="{end_id}" name="پایان"/>')
        node_types[end_id] = "end"
        node_columns[end_id] = node_columns[join_id] + 1
        node_rows[end_id] = 0
        nodes_order.append(end_id)

        # Flows
        flow_index = 1

        def add_flow(src: str, dst: str):
            nonlocal flow_index
            fid = f"Flow_{flow_index}"
            flow_index += 1
            edges.append((fid, src, dst))
            return fid

        add_flow(start_id, pre_task_ids[0] if pre_task_ids else split_id)
        for a, b in zip(pre_task_ids, pre_task_ids[1:]):
            add_flow(a, b)
        if pre_task_ids:
            add_flow(pre_task_ids[-1], split_id)

        # connect split to branch starts
        for bid in branch_start_ids:
            add_flow(split_id, bid)
        # connect internal edges within branches (e.g., no -> follow)
        for a, b in branch_internal_edges:
            add_flow(a, b)
        # connect each branch end to join
        for bid in branch_end_ids:
            add_flow(bid, join_id)

        add_flow(join_id, end_id)

        # Process XML: sequenceFlows
        for fid, src, dst in edges:
            process_elements.append(
                f'<bpmn:sequenceFlow id="{fid}" sourceRef="{src}" targetRef="{dst}"/>'
            )

        process_xml = "\n      ".join(process_elements)

        shapes_xml, edges_xml = _build_diagrams_complex(
            nodes_order,
            edges,
            label_lines_by_id,
            node_columns,
            node_rows,
            node_types,
        )

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
                  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
                  id="Definitions_1"
                  targetNamespace="http://example.com/bpmn">
  <bpmn:process id="{process_id}" isExecutable="false">
      {process_xml}
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="{process_id}">
      {shapes_xml}
      {edges_xml}
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>
"""
    else:
        # Fallback: simple linear diagram
        wrapped_steps = [_format_label_with_role(step) for step in steps]
        task_ids = [
            f"Activity_{index+1}" for index in range(len(wrapped_steps))]
        flow_ids = [f"Flow_{index+1}" for index in range(len(steps) + 1)]

        process_elements = [
            f'<bpmn:startEvent id="{start_id}" name="شروع"/>',
        ]

        label_lines_by_id: Dict[str, int] = {}
        for task_id, label in zip(task_ids, wrapped_steps):
            process_elements.append(
                f'<bpmn:task id="{task_id}" name="{escape(label)}"/>'
            )
            label_lines_by_id[task_id] = label.count("\n") + 1

        process_elements.append(f'<bpmn:endEvent id="{end_id}" name="پایان"/>')

        sequence_flows = []
        all_nodes = [start_id] + task_ids + [end_id]

        for index, flow_id in enumerate(flow_ids):
            source = all_nodes[index]
            target = all_nodes[index + 1]
            sequence_flows.append(
                f'<bpmn:sequenceFlow id="{flow_id}" sourceRef="{source}" targetRef="{target}"/>'
            )

        process_xml = "\n      ".join(process_elements + sequence_flows)

        shapes_xml, edges_xml = _build_diagrams(
            all_nodes, flow_ids, label_lines_by_id)

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
                  xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
                  id="Definitions_1"
                  targetNamespace="http://example.com/bpmn">
  <bpmn:process id="{process_id}" isExecutable="false">
      {process_xml}
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="{process_id}">
      {shapes_xml}
      {edges_xml}
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>
"""


def _extract_steps(user_text: str) -> List[str]:
    """
    Extract candidate steps from user text using simple heuristics.
    """
    # Drop trailing role summary sections like "در کل، فرایند شامل ..."
    summary_cut = re.split(r"در\s+کل\s*،?\s*فرایند\s+شامل.*", user_text, flags=re.IGNORECASE | re.DOTALL)[0]

    cleaned = re.sub(r"\s+", " ", summary_cut.strip())
    if not cleaned:
        return []

    connectors = [
        r"\bthen\b",
        r"\band then\b",
        r"\bafterwards\b",
        r"\bafter that\b",
        r"\bfinally\b",
        r"\bat last\b",
        r"\bultimately\b",
        r"\bsubsequently\b",
        r"\bnext\b",
        r"\band\b",
        r"سپس",
        r"بعداً",
        r"بعد از آن",
        r"در نهایت",
        r"و سپس",
        r"و در نهایت",
    ]

    headline_match = re.search(
        r"\b(includes|consists of|comprises|شامل|متشکل از)\b", cleaned, re.IGNORECASE
    )
    if headline_match:
        cleaned = cleaned[headline_match.end():].strip(" :،,")

    normalized = cleaned
    for connector in connectors:
        normalized = re.sub(
            connector,
            ".",
            normalized,
            flags=re.IGNORECASE,
        )

    primary_fragments = re.split(r"[.\n\r؛]", normalized)
    steps: List[str] = []

    comma_split_pattern = re.compile(
        r",[ ]*(?=(?:and|then|after|finally|در نهایت|سپس|و)\b)", re.IGNORECASE
    )

    for fragment in primary_fragments:
        fragment = fragment.strip(" -:،,")
        if not fragment:
            continue

        sub_fragments = comma_split_pattern.split(fragment)
        for sub in sub_fragments:
            sub = sub.strip(" -:،,")
            if sub:
                sub = re.sub(
                    r"^(?:and|then|after|finally|next|ultimately|در نهایت|سپس|بعداً|بعد از آن|و|و سپس)\b[\s،]*",
                    "",
                    sub,
                    flags=re.IGNORECASE,
                )
                if sub:
                    steps.append(sub)

    return steps


def _detect_branch(user_text: str) -> Optional[Dict[str, str]]:
    """
    Detect a simple Persian branching structure like:
    '... اگر <condition> باشد، <yes>. اما اگر <alt> <no>. <after_no>'
    Returns a dict with question, yes_action, no_action, and optional after_no_action.
    """
    text = re.sub(r"\s+", " ", user_text.strip())
    if "اگر" not in text:
        return None

    # Normalize punctuation to make regex predictable
    norm = (
        text.replace("،", ",")
        .replace("؛", ";")
        .replace("‌", "")  # remove zero-width non-joiner to simplify regex
    )

    # Capture until the next period after 'اما اگر' to avoid trailing fragments
    m = re.search(
        r"اگر\s+(?P<cond>.+?)\s*(?:باشد|است)?\s*,\s*(?P<yes>.+?)\s*(?:\.|\s+)?\s*(?:اما|ولی)\s+اگر\s+(?P<no_clause>[^.]+?)(?:\.|\s*$)",
        norm,
        flags=re.IGNORECASE,
    )
    if not m:
        # Persian form without 'اگر': 'در صورتی که <cond> (باشد|است)، <yes> ؛ اما در صورتی که <cond2> (باشد|است)، <no>.'
        m_alt = re.search(
            r"در\s+صورتی\s+که\s+(?P<cond>.+?)\s*(?:باشد|است)?\s*[,،]\s*(?P<yes>.+?)\s*(?:[.;؛]|$)\s*(?:اما|ولی)\s+در\s+صورتی\s+که\s+(?P<no_cond>.+?)\s*(?:باشد|است)?\s*[,،]\s*(?P<no>.+?)(?:[.;؛]|\s*$)",
            norm,
            flags=re.IGNORECASE,
        )
        if not m_alt:
            # Paragraph style with colon after condition:
            # "اگر <cond> : <yes> ...  اگر <cond2> : <no> ..."
            m_par = re.search(
                r"اگر\s+(?P<cond>[^:]+):\s*(?P<yes>.+?)\s*(?:اما|ولی)?\s*اگر\s+(?P<no_cond>[^:]+):\s*(?P<no>.+)",
                user_text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if not m_par:
                return None
            condition = re.sub(r"\s+", " ", m_par.group("cond")).strip()
            yes_action = re.sub(r"\s+", " ", m_par.group("yes")).strip()
            no_action = re.sub(r"\s+", " ", m_par.group("no")).strip()
            remainder = ""
            after_no_action = ""
        else:
            condition = m_alt.group("cond").strip()
            yes_action = m_alt.group("yes").strip()
            no_action = m_alt.group("no").strip()
            # Remainder after the matched alt pattern (follow-up for no-branch)
            remainder = norm[m_alt.end():].strip()
            after_no_action = ""
            if remainder:
                after_no_action = re.split(
                    r"[.;]", remainder, maxsplit=1)[0].strip()
    else:
        condition = m.group("cond").strip()
        yes_action = m.group("yes").strip()
        no_action = m.group("no_clause").strip()
        remainder = norm[m.end():].strip()
        after_no_action = ""
        if remainder:
            after_no_action = re.split(
                r"[.;]", remainder, maxsplit=1)[0].strip()

    question = _normalize_condition(condition)

    result: Dict[str, str] = {
        "question": question,
        "yes_action": yes_action,
        "no_action": no_action,
    }

    # Heuristic: prefix role 'کارشناس' if context implies it
    context_has_expert = "کارشناس" in text
    if context_has_expert:
        if "کارشناس" not in result["yes_action"]:
            result["yes_action"] = "کارشناس " + result["yes_action"]
        if "کارشناس" not in result["no_action"]:
            result["no_action"] = "کارشناس " + result["no_action"]
        if after_no_action and "کارشناس" in after_no_action and "ستاد" in after_no_action:
            # keep as is
            pass

    if after_no_action:
        result["after_no_action"] = after_no_action
    return result


def _normalize_condition(text: str) -> str:
    text = text.strip()
    # For Persian: turn 'قابل پاسخ گویی' into 'قابل پاسخ‌گویی؟'
    text = re.sub(r"\s+", " ", text)
    # Normalize 'باشد' → 'است'
    text = re.sub(r"\bباشد\b", "است", text)
    if not text.endswith("؟"):
        text = f"{text}؟"
    return text


def _detect_multi_branch(user_text: str) -> Optional[Dict[str, List[str]]]:
    """
    Detect multiple simple 'اگر ... بود/باشد ...' branches in a row.
    Returns dict with 'question' and 'branches' (list of actions) if >=2 found.
    """
    text = re.sub(r"\s+", " ", user_text)
    # Find all 'اگر <cond> (بود|باشد|است)? <action>' occurrences
    pattern = re.compile(
        r"اگر\s+(.+?)(?:\s+(?:بود|باشد|است))?\s*[:،,]?\s*(.+?)(?=(?:\s+(?:و\s+)?اگر\b)|$)",
        re.IGNORECASE,
    )
    matches = pattern.findall(text)
    if len(matches) < 2:
        return None
    actions: List[str] = []
    for (_cond, action) in matches:
        cleaned_action = action.strip()
        # Trim trailing punctuation
        cleaned_action = re.sub(r"[.؛]+$", "", cleaned_action)
        actions.append(cleaned_action)
    return {"question": "تصمیم‌گیری", "branches": actions}


def _format_label_with_role(step: str) -> str:
    return _wrap_label(_label_with_role(step))


def _format_label_with_role_direct(action: str) -> str:
    return _wrap_label(_label_with_role(action))


def _label_with_role(text: str) -> str:
    """
    Extract role keywords and place them on the first line, then a divider, then action.
    """
    roles = [
        "کارشناس ارشد پشتیبانی ستاد",
        "کارشناس ارشد",
        "کارشناس بررسی شکایت",
        "کارشناس پشتیبانی",
        "کارشناس شکایت ستاد",
        "کارشناس ستاد",
        "کارشناس اولیه",
        "کارشناس",
        "کارمند",
        "کاربر",
    ]
    role_found = ""
    for role in roles:
        if role in text:
            role_found = role
            text = text.replace(role, "")
            break
    # Remove generic prefaces like 'فرایند ... به شرح زیر میباشد'
    text = re.sub(
        r"فرایند.+?(?:به شرح (?:ذیل|زیر) (?:میباشد|است)?:?)", "", text)
    action = text.strip(" :،,-")
    if role_found:
        return f"{role_found}\n—\n{action}"
    return action


def _wrap_label(text: str, max_chars: int = 24) -> str:
    """
    Insert line breaks to fit labels into tasks. Wraps by words.
    """
    words = text.split()
    if not words:
        return text

    lines: List[str] = []
    current: List[str] = []
    current_len = 0

    for word in words:
        sep = 1 if current else 0
        if current_len + sep + len(word) > max_chars:
            lines.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            if sep:
                current_len += 1
            current.append(word)
            current_len += len(word)

    if current:
        lines.append(" ".join(current))

    return "\n".join(lines)


def _build_diagrams(
    nodes: List[str], flow_ids: List[str], label_lines_by_id: Dict[str, int]
) -> Tuple[str, str]:
    """
    Construct BPMN DI definitions (shapes and edges) for a simple linear diagram.
    """
    shapes = []
    edges = []

    start_x = 100
    y = 150
    spacing = 220

    bounds: Dict[str, Tuple[float, float, float, float]] = {}

    for index, node_id in enumerate(nodes):
        x = start_x + spacing * index

        if node_id.startswith("StartEvent"):
            width = height = 36
        elif node_id.startswith("EndEvent"):
            width = height = 36
        else:
            width = 160
            base_height = 80
            lines = max(1, label_lines_by_id.get(node_id, 1))
            extra = max(0, lines - 2)
            height = base_height + extra * 18
            x -= width / 2 - 18  # compensate to align with flow

        bounds[node_id] = (x, y, width, height)

        shapes.append(
            f"""<bpmndi:BPMNShape id="{node_id}_di" bpmnElement="{node_id}">
        <dc:Bounds x="{x:.0f}" y="{y:.0f}" width="{width}" height="{height}"/>
      </bpmndi:BPMNShape>"""
        )

    for index, flow_id in enumerate(flow_ids):
        source_node = nodes[index]
        target_node = nodes[index + 1]

        sx, sy, sw, sh = bounds[source_node]
        tx, ty, tw, th = bounds[target_node]

        source_x = sx + sw
        source_y = sy + sh / 2
        target_x = tx
        target_y = ty + th / 2

        edges.append(
            f"""<bpmndi:BPMNEdge id="{flow_id}_di" bpmnElement="{flow_id}">
        <di:waypoint x="{source_x:.0f}" y="{source_y:.0f}"/>
        <di:waypoint x="{target_x:.0f}" y="{target_y:.0f}"/>
      </bpmndi:BPMNEdge>"""
        )

    shapes_xml = "\n      ".join(shapes)
    edges_xml = "\n      ".join(edges)
    return shapes_xml, edges_xml


def _build_diagrams_complex(
    nodes_order: List[str],
    edges: List[Tuple[str, str, str]],
    label_lines_by_id: Dict[str, int],
    node_columns: Dict[str, int],
    node_rows: Dict[str, int],
    node_types: Dict[str, str],
) -> Tuple[str, str]:
    shapes: List[str] = []
    edges_xml: List[str] = []

    start_x = 100
    base_y = 150
    row_spacing = 160
    spacing_x = 220

    bounds: Dict[str, Tuple[float, float, float, float]] = {}

    for node_id in nodes_order:
        col = node_columns.get(node_id, 0)
        row = node_rows.get(node_id, 0)
        x = start_x + spacing_x * col
        y = base_y + row_spacing * row

        node_type = node_types.get(node_id, "task")
        if node_type == "start" or node_type == "end":
            width = height = 36
        elif node_type == "gateway":
            width = height = 50
        else:
            width = 160
            base_height = 80
            lines = max(1, label_lines_by_id.get(node_id, 1))
            extra = max(0, lines - 2)
            height = base_height + extra * 18
            x -= width / 2 - 18

        bounds[node_id] = (x, y, width, height)
        shapes.append(
            f"""<bpmndi:BPMNShape id="{node_id}_di" bpmnElement="{node_id}">
        <dc:Bounds x="{x:.0f}" y="{y:.0f}" width="{width}" height="{height}"/>
      </bpmndi:BPMNShape>"""
        )

    for fid, src, dst in edges:
        sx, sy, sw, sh = bounds[src]
        tx, ty, tw, th = bounds[dst]
        source_x = sx + sw
        source_y = sy + sh / 2
        target_x = tx
        target_y = ty + th / 2
        edges_xml.append(
            f"""<bpmndi:BPMNEdge id="{fid}_di" bpmnElement="{fid}">
        <di:waypoint x="{source_x:.0f}" y="{source_y:.0f}"/>
        <di:waypoint x="{target_x:.0f}" y="{target_y:.0f}"/>
      </bpmndi:BPMNEdge>"""
        )

    return "\n      ".join(shapes), "\n      ".join(edges_xml)
