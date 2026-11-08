"""Validate the regression fixed after beta.1's iOS 18 import."""

import plistlib
import re
import sys
from pathlib import Path


ROUTES = {
    "manage_apps", "data", "settings", "download", "open_apps",
    "shortcut_update", "about", "language", "home_screen", "limit",
    "edit_icon", "backup", "store", "delete_app", "add_app",
}
PREFIX = "is.workflow.actions."


def references(value):
    if isinstance(value, dict):
        if "OutputUUID" in value:
            yield value["OutputUUID"]
        for child in value.values():
            yield from references(child)
    elif isinstance(value, list):
        for child in value:
            yield from references(child)


def route_guard(action):
    if action["WFWorkflowActionIdentifier"] != PREFIX + "text.match":
        return None
    parameters = action["WFWorkflowActionParameters"]
    values = parameters["text"]["Value"].get("attachmentsByRange", {}).values()
    if not any(value.get("VariableName") == "Route" for value in values):
        return None
    pattern = parameters["WFMatchTextPattern"]
    match = re.fullmatch(r"\\A([a-z_]+)\\z", pattern)
    assert match, pattern
    return match[1]


def check(workflow):
    actions = workflow["WFWorkflowActions"]
    route_ids = set()
    route_groups = {}
    downloads = 0
    seen = set()
    stack = []
    for i, action in enumerate(actions):
        parameters = action["WFWorkflowActionParameters"]
        kind = action["WFWorkflowActionIdentifier"]
        assert set(references(parameters)) <= seen, (i, kind)
        if "UUID" in parameters:
            assert parameters["UUID"] not in seen, (i, kind)
            seen.add(parameters["UUID"])
        if kind == PREFIX + "conditional" and parameters.get("WFControlFlowMode") == 0:
            left = parameters["WFInput"]["Variable"]["Value"]
            if left.get("VariableName") == "Route":
                assert parameters["WFCondition"] in (100, 101), (i, "untyped Route comparison")
        route = route_guard(action)
        if route:
            assert route not in route_ids, route
            route_ids.add(route)
            following = actions[i + 1]
            guard = following["WFWorkflowActionParameters"]
            assert following["WFWorkflowActionIdentifier"] == PREFIX + "conditional"
            assert guard["WFControlFlowMode"] == 0 and guard["WFCondition"] == 100
            assert guard["WFInput"]["Variable"]["Value"]["OutputUUID"] == parameters["UUID"]
            route_groups[guard["GroupingIdentifier"]] = route
            expression = re.compile(parameters["WFMatchTextPattern"].replace(r"\z", r"\Z"))
            assert expression.search(route)
            assert not any(expression.search(bad) for bad in ("", route + "_extra", "x_" + route, route + "\n"))
        if "GroupingIdentifier" in parameters:
            group = (kind, parameters["GroupingIdentifier"])
            if parameters["WFControlFlowMode"] == 0:
                stack.append(group)
            else:
                assert stack and group == stack[-1], (i, group)
                if parameters["WFControlFlowMode"] == 2:
                    stack.pop()
        if kind == PREFIX + "downloadurl":
            assert stack and route_groups.get(stack[0][1]) == "download"
            downloads += 1
    assert not stack and route_ids == ROUTES and downloads == 2
    assert not any(v in plistlib.dumps(workflow) for v in (b"?token=", b"fileProviderDomainID", b"crossDeviceItemID"))
    print(f"Validated {len(route_ids)} exact routes, {downloads} download actions and {len(actions)} workflow actions")


if __name__ == "__main__":
    check(plistlib.loads(Path(sys.argv[1]).read_bytes()))
