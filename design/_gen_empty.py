#!/usr/bin/env python3
"""Generate CloneLM-empty.excalidraw — the cold-start / empty workspace state
(no sources added yet). Mirrors the MCP view into the on-disk Excalidraw schema.
"""
import json
import random
import time

NOW = int(time.time() * 1000)


def nonce():
    return random.randint(1, 2_000_000_000)


def base(el):
    el.setdefault("angle", 0)
    el.setdefault("strokeColor", "#1e1e1e")
    el.setdefault("backgroundColor", "transparent")
    el.setdefault("fillStyle", "solid")
    el.setdefault("strokeWidth", 2)
    el.setdefault("strokeStyle", "solid")
    el.setdefault("roughness", 1)
    el.setdefault("opacity", 100)
    el.setdefault("groupIds", [])
    el.setdefault("frameId", None)
    el.setdefault("roundness", None)
    el.setdefault("seed", nonce())
    el.setdefault("version", 1)
    el.setdefault("versionNonce", nonce())
    el.setdefault("isDeleted", False)
    el.setdefault("boundElements", None)
    el.setdefault("updated", NOW)
    el.setdefault("link", None)
    el.setdefault("locked", False)
    return el


def text_dims(text, fs):
    lines = text.split("\n")
    w = max(len(l) for l in lines) * fs * 0.55
    h = len(lines) * fs * 1.25
    return w, h


elements = []


def shape(kind, id, x, y, w, h, bg="transparent", stroke="#1e1e1e", sw=2,
          rounded=False, label=None, fs=16, dash=False, opacity=100):
    el = base({
        "type": kind, "id": id, "x": x, "y": y, "width": w, "height": h,
        "strokeColor": stroke, "backgroundColor": bg, "strokeWidth": sw,
        "opacity": opacity,
    })
    if dash:
        el["strokeStyle"] = "dashed"
    if rounded:
        el["roundness"] = {"type": 3}
    if label is not None:
        tid = id + "_t"
        el["boundElements"] = [{"type": "text", "id": tid}]
        tw, th = text_dims(label, fs)
        elements.append(el)
        elements.append(base({
            "type": "text", "id": tid,
            "x": x + (w - tw) / 2, "y": y + (h - th) / 2,
            "width": tw, "height": th, "opacity": opacity,
            "fontSize": fs, "fontFamily": 1, "text": label,
            "textAlign": "center", "verticalAlign": "middle",
            "containerId": id, "originalText": label, "lineHeight": 1.25,
            "baseline": round(fs * 0.9),
        }))
        return
    elements.append(el)


def text(id, x, y, t, fs=16, color="#1e1e1e"):
    tw, th = text_dims(t, fs)
    elements.append(base({
        "type": "text", "id": id, "x": x, "y": y, "width": tw, "height": th,
        "strokeColor": color, "fontSize": fs, "fontFamily": 1, "text": t,
        "textAlign": "left", "verticalAlign": "top", "containerId": None,
        "originalText": t, "lineHeight": 1.25, "baseline": round(fs * 0.9),
    }))


def line(id, x, y, dx, color="#ced4da", sw=1):
    elements.append(base({
        "type": "arrow", "id": id, "x": x, "y": y, "width": dx, "height": 0,
        "strokeColor": color, "strokeWidth": sw, "points": [[0, 0], [dx, 0]],
        "startArrowhead": None, "endArrowhead": None, "roundness": {"type": 2},
        "lastCommittedPoint": None, "startBinding": None, "endBinding": None,
    }))


# ---- frame + top bar ----
shape("rectangle", "frame", 40, 86, 1120, 632, bg="#ffffff", stroke="#adb5bd", sw=1, rounded=True)
shape("rectangle", "topbar", 40, 86, 1120, 52, bg="#dbe4ff", stroke="#adb5bd", sw=1)
shape("ellipse", "logo", 56, 98, 28, 28, bg="#4a9eed", stroke="#1971c2")
text("brand", 92, 100, "CloneLM", 22, "#1971c2")
text("nbtitle", 214, 104, "·  Unbenanntes Notebook", 15, "#495057")
shape("rectangle", "btnNew", 748, 98, 160, 30, bg="#a5d8ff", stroke="#1971c2", rounded=True, label="+ Neues Notebook", fs=14)
shape("rectangle", "btnShare", 920, 98, 86, 30, bg="#ffffff", stroke="#adb5bd", rounded=True, label="Teilen", fs=14)
shape("rectangle", "btnSet", 1018, 98, 126, 30, bg="#ffffff", stroke="#adb5bd", rounded=True, label="Einstellungen", fs=14)

# ---- sources panel (empty) ----
shape("rectangle", "srcPanel", 56, 150, 300, 556, bg="#dbe4ff", stroke="#4a9eed", sw=1, rounded=True)
text("srcH", 72, 160, "Quellen", 18, "#1971c2")
shape("rectangle", "srcAdd", 72, 188, 268, 40, bg="#a5d8ff", stroke="#1971c2", rounded=True, label="+ Quellen hinzufügen", fs=15)
shape("rectangle", "srcWeb", 72, 240, 268, 44, bg="#ffffff", stroke="#adb5bd", rounded=True, label="Web-Recherche", fs=14)
shape("rectangle", "docIcon", 186, 384, 40, 52, bg="#f8f9fa", stroke="#adb5bd", sw=1, rounded=True)
line("dl1", 194, 400, 24)
line("dl2", 194, 410, 24)
line("dl3", 194, 420, 18)
text("emptyT1", 118, 452, "Gespeicherte Quellen\nwerden hier angezeigt", 15, "#495057")
text("emptyT2", 112, 504, "Klicken Sie auf „Quellen\nhinzufügen“, um PDFs,\nWebsites, Text, Videos\noder Audio hinzuzufügen.", 12, "#757575")

# ---- chat panel (empty) ----
shape("rectangle", "chatPanel", 372, 150, 476, 556, bg="#ffffff", stroke="#adb5bd", sw=1, rounded=True)
text("chatH", 388, 160, "Chat", 18, "#495057")
shape("rectangle", "book", 588, 198, 44, 40, bg="#ffd8a8", stroke="#e8590c", rounded=True)
text("chatTitle", 478, 256, "Unbenanntes Notebook", 24, "#1e1e1e")
text("chatMeta", 533, 292, "0 Quellen · 19.06.2026", 14, "#757575")
shape("rectangle", "hintBox", 452, 408, 316, 64, bg="#f8f9fa", stroke="#ced4da", rounded=True, dash=True)
text("hintT", 500, 420, "Fügen Sie eine Quelle hinzu,\num Fragen zu stellen.", 14, "#757575")
shape("rectangle", "chatIn", 388, 652, 444, 44, bg="#f8f9fa", stroke="#ced4da", rounded=True)
text("chatPh", 404, 666, "Text eingeben…", 15, "#adb5bd")
text("chatCnt", 716, 667, "0 Quellen", 13, "#868e96")
shape("ellipse", "chatSend", 796, 660, 30, 30, bg="#ced4da", stroke="#adb5bd")

# ---- studio panel (tiles disabled) ----
shape("rectangle", "stuPanel", 864, 150, 280, 556, bg="#e5dbff", stroke="#8b5cf6", sw=1, rounded=True)
text("stuH", 880, 160, "Studio", 18, "#6741d9")
shape("rectangle", "st1", 880, 192, 120, 56, bg="#d0bfff", stroke="#6741d9", rounded=True, label="Zusammenfassung", fs=13, opacity=45)
shape("rectangle", "st2", 1012, 192, 120, 56, bg="#c3fae8", stroke="#0c8599", rounded=True, label="FAQ", fs=14, opacity=45)
shape("rectangle", "st3", 880, 256, 120, 56, bg="#ffd8a8", stroke="#e8590c", rounded=True, label="Study Guide", fs=14, opacity=45)
shape("rectangle", "st4", 1012, 256, 120, 56, bg="#b2f2bb", stroke="#2f9e44", rounded=True, label="Briefing", fs=14, opacity=45)
shape("rectangle", "st5", 880, 320, 120, 56, bg="#a5d8ff", stroke="#1971c2", rounded=True, label="Timeline", fs=14, opacity=45)
shape("rectangle", "st6", 1012, 320, 120, 56, bg="#eebefa", stroke="#ae3ec9", rounded=True, label="Audio (Stretch)", fs=13, opacity=45)
text("stuE1", 906, 420, "Hier wird die Ausgabe von\nStudio gespeichert.", 14, "#495057")
text("stuE2", 900, 472, "Nachdem Sie Quellen hinzu-\ngefügt haben, erstellen Sie\nAudio-Übersichten, Arbeits-\nhilfen, Mindmaps u. v. m.", 12, "#757575")
shape("rectangle", "stuNotiz", 916, 650, 180, 38, bg="#ffffff", stroke="#343a40", rounded=True, label="+ Notiz hinzufügen", fs=14)

# ---- empty-state behaviour note ----
shape("rectangle", "note", 60, 742, 1040, 44, bg="#fff3bf", stroke="#f59e0b", rounded=True,
      label="Empty State · 0 Quellen → Chat-Eingabe & Studio-Tiles deaktiviert, bis ≥ 1 Quelle den Status „bereit“ erreicht.  Erste Aktion: „+ Quellen hinzufügen“.", fs=13)

doc = {
    "type": "excalidraw",
    "version": 2,
    "source": "https://excalidraw.com",
    "elements": elements,
    "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
    "files": {},
}

with open("/home/robin/Projects/Everlast/design/CloneLM-empty.excalidraw", "w") as f:
    json.dump(doc, f, ensure_ascii=False, indent=2)

print("wrote", len(elements), "elements")
