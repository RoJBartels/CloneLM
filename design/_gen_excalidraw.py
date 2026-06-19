#!/usr/bin/env python3
"""Generate a valid .excalidraw file for the CloneLM frontend draft.

Re-encodes the MCP Excalidraw view (labels + camera pseudo-elements) into the
on-disk Excalidraw schema: full element fields, and labels expanded into bound
text elements (containerId + boundElements link).
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
          rounded=False, label=None, fs=16, dash=False):
    el = base({
        "type": kind, "id": id, "x": x, "y": y, "width": w, "height": h,
        "strokeColor": stroke, "backgroundColor": bg, "strokeWidth": sw,
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
            "width": tw, "height": th,
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


def arrow(id, x, y, points, stroke="#1e1e1e", sw=2, label=None, fs=14, dash=False):
    w = max(p[0] for p in points) - min(p[0] for p in points)
    h = max(p[1] for p in points) - min(p[1] for p in points)
    el = base({
        "type": "arrow", "id": id, "x": x, "y": y, "width": w, "height": h,
        "strokeColor": stroke, "strokeWidth": sw, "points": points,
        "startArrowhead": None, "endArrowhead": "arrow", "roundness": {"type": 2},
        "lastCommittedPoint": None, "startBinding": None, "endBinding": None,
    })
    if dash:
        el["strokeStyle"] = "dashed"
    if label is not None:
        tid = id + "_t"
        el["boundElements"] = [{"type": "text", "id": tid}]
        tw, th = text_dims(label, fs)
        elements.append(el)
        elements.append(base({
            "type": "text", "id": tid,
            "x": x + w / 2 - tw / 2, "y": y + h / 2 - th / 2,
            "width": tw, "height": th, "fontSize": fs, "fontFamily": 1,
            "text": label, "textAlign": "center", "verticalAlign": "middle",
            "containerId": id, "originalText": label, "lineHeight": 1.25,
            "baseline": round(fs * 0.9),
        }))
        return
    elements.append(el)


# ---- frame + top bar ----
shape("rectangle", "frame", 40, 86, 1120, 632, bg="#ffffff", stroke="#adb5bd", sw=1, rounded=True)
shape("rectangle", "topbar", 40, 86, 1120, 52, bg="#dbe4ff", stroke="#adb5bd", sw=1)
shape("ellipse", "logo", 56, 98, 28, 28, bg="#4a9eed", stroke="#1971c2")
text("brand", 92, 100, "CloneLM", 22, "#1971c2")
text("nbtitle", 214, 104, "·  FontAwesome 5 Icon Reference Guide", 15, "#495057")
shape("rectangle", "btnNew", 748, 98, 160, 30, bg="#a5d8ff", stroke="#1971c2", rounded=True, label="+ Neues Notebook", fs=14)
shape("rectangle", "btnShare", 920, 98, 86, 30, bg="#ffffff", stroke="#adb5bd", rounded=True, label="Teilen", fs=14)
shape("rectangle", "btnSet", 1018, 98, 126, 30, bg="#ffffff", stroke="#adb5bd", rounded=True, label="Einstellungen", fs=14)

# ---- sources panel ----
shape("rectangle", "srcPanel", 56, 150, 300, 556, bg="#dbe4ff", stroke="#4a9eed", sw=1, rounded=True)
text("srcH", 72, 160, "Quellen", 18, "#1971c2")
shape("rectangle", "srcAdd", 72, 188, 268, 40, bg="#ffffff", stroke="#4a9eed", rounded=True, label="+ Quellen hinzufügen", fs=15)
shape("rectangle", "srcWeb", 72, 240, 268, 44, bg="#ffffff", stroke="#adb5bd", rounded=True, label="Web-Recherche", fs=14)
text("srcAll", 222, 298, "Alle auswählen", 14, "#495057")
shape("rectangle", "srcAllBox", 326, 296, 18, 18, bg="#4a9eed", stroke="#1971c2")
shape("rectangle", "srcItem", 72, 322, 268, 46, bg="#ffffff", stroke="#adb5bd", rounded=True)
shape("rectangle", "srcPdf", 84, 333, 44, 24, bg="#ffc9c9", stroke="#ef4444", rounded=True, label="PDF", fs=14)
text("srcFile", 138, 336, "fontawesome5Icons.pdf", 14, "#1e1e1e")
shape("rectangle", "srcChk", 318, 336, 16, 16, bg="#4a9eed", stroke="#1971c2")
shape("rectangle", "srcStat", 84, 376, 92, 24, bg="#b2f2bb", stroke="#2f9e44", rounded=True, label="bereit", fs=14)
shape("rectangle", "srcNote", 72, 628, 268, 64, bg="#fff3bf", stroke="#f59e0b", rounded=True, label="Track A · POST/GET /sources\nstatus: processing → ready", fs=14)

# ---- chat panel ----
shape("rectangle", "chatPanel", 372, 150, 476, 556, bg="#ffffff", stroke="#adb5bd", sw=1, rounded=True)
text("chatH", 388, 160, "Chat", 18, "#495057")
text("chatTitle", 388, 194, "FontAwesome 5 Icon Reference Guide", 20, "#1e1e1e")
text("chatMeta", 388, 224, "1 Quelle · 19.06.2026", 14, "#757575")
shape("rectangle", "ansBub", 388, 250, 444, 118, bg="#f1f3f5", stroke="#ced4da", rounded=True)
text("ansTxt", 404, 262, "Das Dokument listet FontAwesome-5-Symbole für\nLaTeX auf: Marken-Logos, Werkzeuge, Währungen\nund Fahrzeuge — jeweils mit zugehörigem Befehl.", 15, "#1e1e1e")
shape("rectangle", "cite1", 404, 334, 34, 24, bg="#ffd8a8", stroke="#f59e0b", rounded=True, label="[1]", fs=14)
shape("rectangle", "actSave", 388, 384, 170, 30, bg="#ffffff", stroke="#adb5bd", rounded=True, label="In Notiz speichern", fs=14)
shape("rectangle", "actUp", 566, 384, 34, 30, bg="#ffffff", stroke="#adb5bd", rounded=True, label="+", fs=14)
shape("rectangle", "sug1", 388, 430, 420, 34, bg="#f1f3f5", stroke="#ced4da", rounded=True, label="Welche Icon-Kategorien enthält das Paket?", fs=14)
shape("rectangle", "sug2", 388, 472, 420, 34, bg="#f1f3f5", stroke="#ced4da", rounded=True, label="Wie finde ich Social-Media-Symbole?", fs=14)
shape("rectangle", "chatNote", 388, 524, 444, 42, bg="#fff3bf", stroke="#f59e0b", rounded=True, label="Track B · POST /chat (SSE) · Citation-IDs · Refusal bei fehlender Quelle", fs=13)
shape("rectangle", "chatIn", 388, 652, 444, 44, bg="#ffffff", stroke="#4a9eed", rounded=True)
text("chatPh", 404, 666, "Text eingeben…", 15, "#757575")
shape("ellipse", "chatSend", 796, 660, 30, 30, bg="#4a9eed", stroke="#1971c2")

# ---- studio panel ----
shape("rectangle", "stuPanel", 864, 150, 280, 556, bg="#e5dbff", stroke="#8b5cf6", sw=1, rounded=True)
text("stuH", 880, 160, "Studio", 18, "#6741d9")
shape("rectangle", "st1", 880, 192, 120, 56, bg="#d0bfff", stroke="#6741d9", rounded=True, label="Zusammenfassung", fs=13)
shape("rectangle", "st2", 1012, 192, 120, 56, bg="#c3fae8", stroke="#0c8599", rounded=True, label="FAQ", fs=14)
shape("rectangle", "st3", 880, 256, 120, 56, bg="#ffd8a8", stroke="#e8590c", rounded=True, label="Study Guide", fs=14)
shape("rectangle", "st4", 1012, 256, 120, 56, bg="#b2f2bb", stroke="#2f9e44", rounded=True, label="Briefing", fs=14)
shape("rectangle", "st5", 880, 320, 120, 56, bg="#a5d8ff", stroke="#1971c2", rounded=True, label="Timeline", fs=14)
shape("rectangle", "st6", 1012, 320, 120, 56, bg="#eebefa", stroke="#ae3ec9", rounded=True, label="Audio (Stretch)", fs=13)
shape("rectangle", "stuOut", 880, 400, 252, 104, bg="#ffffff", stroke="#adb5bd", rounded=True)
text("stuOutT", 908, 426, "Generierte Artefakte\n(als Notiz speicherbar)", 14, "#757575")
shape("rectangle", "stuNote", 880, 520, 252, 56, bg="#fff3bf", stroke="#f59e0b", rounded=True, label="Track E · POST /studio (kind=…)\ngegroundet + zitiert", fs=13)
shape("rectangle", "stuNotiz", 916, 650, 180, 38, bg="#ffffff", stroke="#343a40", rounded=True, label="+ Notiz hinzufügen", fs=14)

# ---- legend ----
text("legT", 56, 728, "Farb-Mapping → Backend-Track:", 15, "#495057")
shape("rectangle", "lg1", 336, 726, 18, 18, bg="#dbe4ff", stroke="#4a9eed")
text("lg1t", 360, 728, "Quellen = Ingestion (A)", 13, "#495057")
shape("rectangle", "lg2", 596, 726, 18, 18, bg="#ffffff", stroke="#adb5bd")
text("lg2t", 620, 728, "Chat = Retrieval+Chat (B)", 13, "#495057")
shape("rectangle", "lg3", 872, 726, 18, 18, bg="#e5dbff", stroke="#8b5cf6")
text("lg3t", 896, 728, "Studio (E) / Notes (D)", 13, "#495057")

# ---- modal-overlays section (drawn below the main view) ----
text("secT", 60, 768, "Modale Overlays — erscheinen über der Hauptansicht", 18, "#6741d9")

# upload modal (trigger: "+ Quellen hinzufügen")
arrow("upArr", 72, 212, [[0, 0], [-26, 0], [-26, 592], [-12, 592]], stroke="#4a9eed", sw=2, dash=True, label="öffnet", fs=13)
shape("rectangle", "upCard", 60, 804, 540, 372, bg="#ffffff", stroke="#8b5cf6", sw=2, rounded=True)
text("upX", 572, 812, "X", 18, "#868e96")
text("upTitle", 84, 820, "Quellen hinzufügen", 20, "#1e1e1e")
text("upTrig", 84, 850, "Trigger: „+ Quellen hinzufügen“ (Quellen-Panel)", 13, "#6741d9")
shape("rectangle", "upWeb", 84, 878, 492, 44, bg="#ffffff", stroke="#4a9eed", rounded=True)
text("upWebT", 100, 892, "Im Web nach neuen Quellen suchen", 14, "#757575")
shape("ellipse", "upMag", 544, 888, 24, 24, bg="transparent", stroke="#4a9eed")
shape("rectangle", "upDrop", 84, 938, 492, 150, bg="#f8f9fa", stroke="#adb5bd", rounded=True, dash=True)
text("upDropT", 202, 952, "oder laden Sie Ihre Dateien hoch", 15, "#495057")
text("upDropS", 172, 978, "PDF · Bilder · Dokumente · Audio · Text · URL", 13, "#757575")
shape("rectangle", "upB1", 96, 1024, 112, 40, bg="#ffffff", stroke="#adb5bd", rounded=True, label="Hochladen", fs=13)
shape("rectangle", "upB2", 218, 1024, 112, 40, bg="#ffffff", stroke="#adb5bd", rounded=True, label="Websites", fs=13)
shape("rectangle", "upB3", 340, 1024, 112, 40, bg="#ffffff", stroke="#adb5bd", rounded=True, label="Drive", fs=13)
shape("rectangle", "upB4", 462, 1024, 112, 40, bg="#ffffff", stroke="#adb5bd", rounded=True, label="Text einfügen", fs=13)
shape("rectangle", "upNote", 84, 1108, 492, 44, bg="#fff3bf", stroke="#f59e0b", rounded=True, label="Track A · POST /sources (type = file | url | paste) → parse · chunk · embed (bge-m3)", fs=12)

# source-viewer modal / "Beleg" (trigger: citation chip [1])
arrow("vwArr", 832, 358, [[0, 0], [24, 0], [24, 446]], stroke="#f59e0b", sw=2, dash=True, label="Klick [1]", fs=13)
shape("rectangle", "vwCard", 640, 804, 480, 320, bg="#ffffff", stroke="#f59e0b", sw=2, rounded=True)
text("vwX", 1092, 812, "X", 18, "#868e96")
text("vwTitle", 664, 820, "Beleg-Ansicht", 20, "#1e1e1e")
text("vwTrig", 664, 850, "Trigger: Klick auf Citation-Chip [1] im Chat", 13, "#6d4400")
text("vwInfo", 664, 874, "fontawesome5Icons.pdf · Seite 3 · Abschnitt „Symbole“", 13, "#757575")
shape("rectangle", "vwRead", 664, 900, 432, 160, bg="#ffffff", stroke="#ced4da", rounded=True)
text("vwL1", 680, 912, "Das LaTeX-Paket FontAwesome5 stellt eine", 13, "#495057")
text("vwL2", 680, 934, "umfangreiche Sammlung von Vektor-Icons bereit.", 13, "#495057")
shape("rectangle", "vwHi", 672, 960, 416, 40, bg="#fff3bf", stroke="#f59e0b", rounded=True)
text("vwHiT", 684, 970, "„…bindet die Icons via LaTeX-Befehl ein…“    [1]", 13, "#5c4400")
text("vwL3", 680, 1012, "Jedes Symbol ist mit Befehl und Vorschau gelistet.", 13, "#495057")
shape("rectangle", "vwNote", 664, 1072, 432, 40, bg="#fff3bf", stroke="#f59e0b", rounded=True, label="Track B · citation → source-span Mapping (start/end char)", fs=12)

doc = {
    "type": "excalidraw",
    "version": 2,
    "source": "https://excalidraw.com",
    "elements": elements,
    "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
    "files": {},
}

with open("/home/robin/Projects/Everlast/design/CloneLM-frontend.excalidraw", "w") as f:
    json.dump(doc, f, ensure_ascii=False, indent=2)

print("wrote", len(elements), "elements")
