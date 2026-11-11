"""Validate exported route conditions and installer bindings for iOS 18."""

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
PACKAGE_FILES = {
    "Core.json", "IconDark.png", "IconLight.png",
    "MenuDark.json", "MenuLight.json", "SystemApps.json",
}


def references(value):
    if isinstance(value, dict):
        if "OutputUUID" in value:
            yield value["OutputUUID"]
        for child in value.values():
            yield from references(child)
    elif isinstance(value, list):
        for child in value:
            yield from references(child)


def check_text_tokens(value):
    if isinstance(value, dict):
        if "string" in value and "attachmentsByRange" in value:
            data = value["string"].encode("utf-16-le")
            tokens = value["attachmentsByRange"]
            assert len(tokens) == value["string"].count("\ufffc")
            for location in tokens:
                offset = int(re.search(r"\d+", location)[0]) * 2
                assert data[offset:offset + 2] == b"\xfc\xff", location
        for child in value.values():
            check_text_tokens(child)
    elif isinstance(value, list):
        for child in value:
            check_text_tokens(child)


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


def check_installer(actions):
    assert all(kind != PREFIX + "count" for kind, _ in actions), "The installer must validate named files"
    assert not any(
        kind in (PREFIX + "number.random", PREFIX + "text.replace") for kind, _ in actions
    ), "The staging name must not depend on formatting a random number"
    pointers = {
        params.get("WFGetFilePath") for kind, params in actions
        if kind == PREFIX + "documentpicker.open" and isinstance(params.get("WFGetFilePath"), str)
    }
    assert {"Active.txt", "Previous.txt"} <= pointers, "Protect both pointers before staging"
    unpack = next(params for kind, params in actions if kind == PREFIX + "unzip")
    writes = [
        (index, params) for index, (kind, params) in enumerate(actions)
        if kind == PREFIX + "documentpicker.save"
    ]
    save_index, stage = next((i, p) for i, p in writes if unpack["UUID"] in references(p["WFInput"]))
    activation, publish = next((i, p) for i, p in writes if p.get("WFFileDestinationPath") == "Active.txt")
    staged_folder = next(
        params for kind, params in actions
        if kind == PREFIX + "file.createfolder" and params["UUID"] in references(stage["WFFolder"])
    )
    slot = publish["WFInput"]["Value"]
    assert slot.get("VariableName") == "InstallSlot"
    assert slot in staged_folder["WFFilePath"]["Value"]["attachmentsByRange"].values()
    assert stage["WFSaveFileOverwrite"] is True, "A partial unprotected slot can be retried"
    validation = actions[save_index + 1:activation]
    names = next(params["WFItems"] for kind, params in validation if kind == PREFIX + "list")
    assert {item["WFValue"]["Value"]["string"] for item in names} == PACKAGE_FILES
    readback = next(params for kind, params in validation if kind == PREFIX + "documentpicker.open")
    assert readback["WFFile"] == stage["WFFolder"] and readback["WFFileErrorIfNotFound"] is False
    assert any(
        kind == PREFIX + "conditional" and params.get("WFCondition") == 101
        and readback["UUID"] in references(params["WFInput"])
        for kind, params in validation
    ), "A missing staged file must block activation"


def check(workflow):
    actions = workflow["WFWorkflowActions"]
    route_ids = set()
    route_groups = {}
    downloads = 0
    installer = []
    seen = set()
    stack = []
    for i, action in enumerate(actions):
        parameters = action["WFWorkflowActionParameters"]
        kind = action["WFWorkflowActionIdentifier"]
        assert set(references(parameters)) <= seen, (i, kind)
        if "UUID" in parameters:
            assert parameters["UUID"] not in seen, (i, kind)
            seen.add(parameters["UUID"])
        if kind == PREFIX + "count":
            assert "Input" in parameters and "WFInput" not in parameters, (i, "Count uses the native Input key")
        if kind == PREFIX + "text.replace":
            assert parameters["WFInput"]["WFSerializationType"] == "WFTextTokenString", (i, "Replace Text needs a visible text source on iOS")
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
        if stack and route_groups.get(stack[0][1]) == "download":
            installer.append((kind, parameters))
        if kind == PREFIX + "downloadurl":
            assert stack and route_groups.get(stack[0][1]) == "download"
            downloads += 1
    assert not stack and route_ids == ROUTES and downloads == 2
    check_installer(installer)
    assert not any(v in plistlib.dumps(workflow) for v in (b"?token=", b"fileProviderDomainID", b"crossDeviceItemID"))
    print(f"Validated {len(route_ids)} exact routes, {downloads} download actions and {len(actions)} workflow actions")


if __name__ == "__main__":
    workflow = plistlib.loads(Path(sys.argv[1]).read_bytes())
    check(workflow)
    check_text_tokens(workflow)
