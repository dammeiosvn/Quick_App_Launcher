"""Run the exported installer and startup actions against local iCloud and ZIP doubles."""

import hashlib
import io
import json
import plistlib
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
DATA = PurePosixPath("Quick App Launcher Data")
USER = PurePosixPath("Quick App Launcher")
LANGUAGE = USER / "LangCode/LangCode.txt"
LIMIT = USER / "LangCode/Limit.txt"
PLUGIN = "Plugin_Quickapplauncher"
ACTION_PREFIX = "is.workflow.actions."


@dataclass(frozen=True)
class File:
    name: str
    data: bytes


class Stop(Exception):
    pass


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def to_text(value):
    if isinstance(value, list):
        return "\n".join(to_text(item) for item in value)
    if isinstance(value, File):
        return value.name
    if isinstance(value, int) and not isinstance(value, bool):
        return format(value, ",d").replace(",", ".")
    return "" if value is None else str(value)


def to_bytes(value):
    return value.data if isinstance(value, File) else to_text(value).encode()


def contacts(value):
    cards = []
    for file in as_list(value):
        if isinstance(file, dict):
            cards.append(file)
            continue
        for part in to_bytes(file).decode().split("BEGIN:VCARD\n")[1:]:
            field = re.search(r"^NOTE:(.*)$", part, re.M)
            if field:
                cards.append({"Notes": field[1]})
    return cards


def pattern(value):
    return value.replace(r"\z", r"\Z")


class Runner:
    def __init__(self, version, files=None, menus=(), routes=(), *, offline=False, drop=None, bad_zip=False, dark=False):
        name = f"Quick-App-Launcher-v2.5.0-beta.{version}.unsigned.shortcut"
        self.actions = [
            (row["WFWorkflowActionIdentifier"].removeprefix(ACTION_PREFIX), row["WFWorkflowActionParameters"])
            for row in plistlib.loads((ROOT / "shortcuts" / name).read_bytes())["WFWorkflowActions"]
        ]
        self.spans = {}
        stack = []
        for index, (_, params) in enumerate(self.actions):
            mode = params.get("WFControlFlowMode")
            if mode == 0:
                stack.append([index, []])
            elif mode == 1:
                stack[-1][1].append(index)
            elif mode == 2:
                start, branches = stack.pop()
                self.spans[start] = (index, branches)
        self.files = dict(files or {})
        self.vars = {}
        self.outputs = {}
        self.menus = deque(menus)
        self.routes = deque(routes)
        self.nonce = iter([123456789, 987654321, 135791357, 246802468])
        self.offline, self.drop, self.bad_zip, self.dark = offline, drop, bad_zip, dark
        self.urls, self.writes, self.notices, self.plugins, self.prompts = [], [], [], [], []
        self.visible_cards = []

    def resolve(self, value):
        if not isinstance(value, dict):
            return value
        if "WFSerializationType" in value:
            return self.resolve(value["Value"])
        if "string" in value:
            text = value["string"]
            ordered = sorted(value.get("attachmentsByRange", {}).items(), key=lambda item: int(re.search(r"\d+", item[0])[0]))
            values = iter(self.resolve(item) for _, item in ordered)
            return re.sub("\ufffc", lambda _: to_text(next(values)), text)
        if value.get("Type") == "Variable" and "Variable" in value:
            return self.resolve(value["Variable"])
        if value.get("Type") == "Variable":
            result = self.vars.get(value["VariableName"])
        elif value.get("Type") == "ActionOutput":
            result = self.outputs.get(value["OutputUUID"])
        else:
            return value
        for modifier in value.get("Aggrandizements", []):
            kind = modifier["Type"]
            if kind == "WFCoercionVariableAggrandizement":
                if modifier["CoercionItemClass"] == "WFContactContentItem":
                    result = contacts(result)
                elif modifier["CoercionItemClass"] == "WFNumberContentItem":
                    result = int(to_text(result).replace(".", ""))
            elif kind == "WFDictionaryValueVariableAggrandizement":
                result = result.get(modifier["DictionaryKey"])
            elif kind == "WFPropertyVariableAggrandizement":
                prop = modifier["PropertyName"]
                if prop == "Keys":
                    result = list(result)
                elif isinstance(result, list):
                    result = [item[prop] for item in result]
                else:
                    result = result[prop]
        return result

    def action(self, kind, params):
        def get(name):
            return self.resolve(params.get(name))

        match kind:
            case "comment" | "nothing":
                return None
            case "gettext":
                return get("WFTextActionText")
            case "setvariable":
                self.vars[params["WFVariableName"]] = get("WFInput")
            case "list":
                return [self.resolve(item["WFValue"]) for item in params["WFItems"]]
            case "file.createfolder":
                parent = get("WFFolder")
                return (parent if isinstance(parent, PurePosixPath) else PurePosixPath()) / get("WFFilePath")
            case "documentpicker.open":
                path = get("WFFile") / get("WFGetFilePath")
                return File(path.name, self.files[path]) if path in self.files else None
            case "documentpicker.save":
                directory = get("WFFolder")
                for value in as_list(get("WFInput")):
                    path = directory / (get("WFFileDestinationPath") or getattr(value, "name", "Text.txt"))
                    if self.drop and directory.parent == DATA and path.name == self.drop:
                        continue
                    assert path not in self.files or params["WFSaveFileOverwrite"], f"An existing file needs overwrite enabled: {path}"
                    self.files[path] = to_bytes(value)
                    self.writes.append(path)
            case "file.getfoldercontents":
                return [File(path.name, data) for path, data in self.files.items() if path.parent == get("WFFolder")]
            case "detect.text":
                return to_bytes(get("WFInput")).decode()
            case "detect.dictionary":
                return json.loads(to_bytes(get("WFInput")))
            case "getvalueforkey":
                return get("WFInput").get(get("WFDictionaryKey"))
            case "text.match":
                return [item[0] for item in re.finditer(pattern(get("WFMatchTextPattern")), get("text"))]
            case "text.combine":
                return to_text(get("text"))
            case "text.replace":
                return re.sub(pattern(get("WFReplaceTextFind")), get("WFReplaceTextReplace"), to_text(get("WFInput")))
            case "number.random":
                return next(self.nonce)
            case "filter.files":
                return sorted(get("WFContentItemInputParameter"))
            case "choosefromlist":
                if get("WFChooseFromListActionPrompt") == "Ngôn ngữ / Language":
                    languages = json.loads((ROOT / "data/Core.json").read_bytes())["languages"]
                    vietnamese = next(label for label, code in languages.items() if code == "vi-VN")
                    assert vietnamese in get("WFInput")
                    return vietnamese
                choices = get("WFInput")
                if all(isinstance(choice, str) for choice in choices):
                    return choices[0]
                self.visible_cards = [choice["Notes"] for choice in choices]
                note = self.routes.popleft()
                return next(choice for choice in choices if choice["Notes"] == note)
            case "setitemname":
                return File(get("WFName"), to_bytes(get("WFInput")))
            case "getdevicedetails":
                return {"Dark Mode Is On": self.dark}
            case "getmyworkflows":
                return [{"Name": PLUGIN}]
            case "runworkflow":
                self.plugins.append(params["WFWorkflowName"])
            case "ask":
                self.prompts.append(get("WFAskActionPrompt"))
                return 30
            case "downloadurl":
                assert not self.offline
                url = get("WFURL")
                self.urls.append(url)
                name = url.rsplit("/", 1)[-1]
                contents = (ROOT / "dist" / name).read_bytes()
                if self.bad_zip and name.endswith(".zip"):
                    contents += b"corrupt"
                return File(name, contents)
            case "hash":
                assert get("WFHashType") == "SHA256"
                return hashlib.sha256(to_bytes(get("WFInput"))).hexdigest()
            case "unzip":
                with ZipFile(io.BytesIO(to_bytes(get("WFArchive")))) as archive:
                    return [File(name, archive.read(name)) for name in archive.namelist()]
            case "count":
                return len(as_list(get("Input")))
            case "alert":
                self.notices.append(get("WFAlertActionMessage"))
            case "exit":
                raise Stop()
            case _:
                raise AssertionError(f"Model does not implement {kind}")

    def execute(self, start, end):
        result = None
        index = start
        while index < end:
            kind, params = self.actions[index]
            if index not in self.spans:
                result = self.action(kind, params)
                output = params.get("UUID")
            else:
                boundary, branches = self.spans[index]
                output = self.actions[boundary][1].get("UUID")
                if kind == "repeat.each":
                    items = as_list(self.resolve(params["WFInput"]))
                    result = []
                    for item in items:
                        self.vars["Repeat Item"] = item
                        result.append(self.execute(index + 1, boundary))
                elif kind == "conditional":
                    left = self.resolve(params["WFInput"])
                    code = params["WFCondition"]
                    if code == 100:
                        yes = bool(left)
                    elif code == 101:
                        yes = not left
                    elif code == 4:
                        yes = bool(left)
                    elif code == 2:
                        yes = left > int(self.resolve(params["WFNumberValue"]))
                    elif code == 3:
                        yes = left >= int(to_text(self.resolve(params["WFNumberValue"])))
                    else:
                        raise AssertionError(code)
                    if yes:
                        result = self.execute(index + 1, branches[0] if branches else boundary)
                    else:
                        result = self.execute(branches[0] + 1, boundary) if branches else None
                elif kind == "choosefrommenu":
                    choice = self.menus.popleft() if self.menus else (2 if to_text(self.resolve(params.get("WFMenuPrompt"))).startswith("Mở nhanh ứng dụng") else self.menus.popleft())
                    result = self.execute(branches[choice] + 1, (branches + [boundary])[choice + 1])
                else:
                    raise AssertionError(kind)
                index = boundary
            if output:
                self.outputs[output] = result
            index += 1
        return result

    def run(self):
        try:
            self.execute(0, len(self.actions))
        except Stop:
            pass
        return self


def main():
    old = Runner(2, menus=[0]).run()
    assert "Unexpected package contents" in old.notices[-1] and len(old.urls) == 2
    print("beta.2 reproduces the recorded post-extract alert when Count reads its native Input field")

    fragile = Runner(3, menus=[0])
    fragile.nonce = iter(["123.456.789,0", "987.654.321,0"])
    fragile.run()
    assert "Invalid data folder" in fragile.notices[-1]
    print("beta.3 rejects its generated name if a random value is formatted with a decimal suffix")

    fresh = Runner(5, menus=[0]).run()
    assert "Đã lưu dữ liệu v1" in fresh.notices[-1]
    active = DATA / "Active.txt"
    slot = fresh.files[active].decode()
    manifest = json.loads((ROOT / "dist/manifest.json").read_bytes())
    stem = f"v1-{manifest['sha256']}"
    assert slot == f"{stem}-a"
    assert fresh.writes[-1] == active
    with ZipFile(ROOT / "dist/launcher-data-v1.zip") as archive:
        for name in archive.namelist():
            assert fresh.files[DATA / slot / name] == archive.read(name)
    print("beta.5 derives its staging name from verified fields, saves all six exact files and activates last")

    warm = Runner(5, fresh.files, routes=["open_apps"], offline=True, dark=True).run()
    assert not warm.urls and warm.plugins == [PLUGIN] and warm.files[LANGUAGE] == b"vi-VN"
    assert warm.visible_cards == ["open_apps", "add_app", "manage_apps", "data", "settings"]
    assert DATA / slot / "Menu-vi-VN-Dark.vcf" in warm.files
    cached = Runner(5, warm.files, routes=["open_apps"], offline=True, dark=True).run()
    assert not cached.urls and not cached.writes and cached.plugins == [PLUGIN]
    print("beta.5 opens five Vietnamese vCards offline and reuses its dark menu cache")

    corrupt = Runner(5, warm.files, menus=[0], routes=["data"], bad_zip=True, dark=True).run()
    assert "checksum mismatch" in corrupt.notices[-1] and corrupt.files == warm.files
    print("beta.5 rejects a corrupted download without changing the current installation")

    retry = Runner(5, warm.files, menus=[0], routes=["data"], dark=True, drop="IconLight.png").run()
    assert "IconLight.png" in retry.notices[-1] and retry.files[active] == warm.files[active]
    assert active not in retry.writes and DATA / "Previous.txt" not in retry.writes
    assert DATA / f"{stem}-b" / "Core.json" in retry.files
    print("beta.5 reports a missing staged file and leaves the current slot usable")

    update = Runner(5, retry.files, menus=[0], routes=["data"], dark=True).run()
    assert update.files[DATA / "Previous.txt"] == fresh.files[active] and update.files[active] != fresh.files[active]
    new_slot = update.files[active].decode()
    assert new_slot == f"{stem}-b" and "Đã lưu dữ liệu v1" in update.notices[-1]
    print("beta.5 retries the partially saved slot successfully")

    for missing in ("Core.json", "MenuDark.json"):
        files = dict(update.files)
        del files[DATA / new_slot / missing]
        fallback = Runner(5, files, routes=["open_apps"], offline=True, dark=True).run()
        assert to_text(fallback.vars["Pack"]) == slot and fallback.plugins == [PLUGIN] and not fallback.urls
    print("beta.5 falls back if the active core or current theme is unavailable")

    damaged = dict(update.files)
    damaged[active] += b"\r\n"
    damaged[DATA / "Previous.txt"] += b"\r\n"
    del damaged[DATA / new_slot / "MenuDark.json"]
    repaired = Runner(5, damaged, menus=[0], routes=["data"], dark=True).run()
    assert repaired.files[active].decode() == f"{stem}-c"
    assert repaired.files[DATA / "Previous.txt"] == slot.encode()
    assert all(path.parent not in (DATA / slot, DATA / new_slot) for path in repaired.writes)
    print("beta.5 protects both pointer targets, including an incomplete active slot and CRLF markers")

    legacy = Runner(3, menus=[0]).run()
    legacy.files[active] += b"\r\n"
    legacy.files[LANGUAGE] = b"vi-VN\r\n"
    compatible = Runner(5, legacy.files, routes=["open_apps"], offline=True).run()
    assert compatible.plugins == [PLUGIN] and to_text(compatible.vars["Codelang"]) == "vi-VN"
    print("beta.5 opens a previous-format slot and reads the saved language with a line ending")

    apps = {USER / "AppList/A.vcf": b"one", USER / "AppList/B.vcf": b"two"}
    settings = Runner(5, warm.files | apps, menus=[1], routes=["settings"], offline=True, dark=True).run()
    assert settings.files[LIMIT] == b"30" and re.search(r"\b2\b", settings.prompts[-1])
    print("beta.5 counts two apps through Count.Input and saves the limit without network access")

    system_app = Runner(5, warm.files, menus=[1], routes=["add_app"], offline=True, dark=True).run()
    new_apps = [path for path in system_app.writes if path.parent == USER / "AppList"]
    assert len(new_apps) == 1 and system_app.files[new_apps[0]].startswith(b"BEGIN:VCARD")
    duplicate = Runner(5, system_app.files, menus=[1], routes=["add_app"], offline=True, dark=True).run()
    assert not duplicate.writes and "Đã có mục cùng tên" in duplicate.notices[-1]
    print("beta.5 adds a system app offline and detects a duplicate before saving")


if __name__ == "__main__":
    main()
