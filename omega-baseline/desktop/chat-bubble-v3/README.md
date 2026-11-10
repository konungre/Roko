# Roko conversation bubble

A transparent GTK 3 / Wayland layer-shell desktop companion. Startup displays
only the emerald/gold avatar. Clicking it opens a character-anchored conversation
bubble. Click the composer to focus it, then type ordinary text and press Enter
or Send. Escape or × dismisses the bubble; Quit exits the companion.

The source includes smooth bounded gliding, pose crossfades, transparent-area
click-through, persistent JSON-lines transport, cancellation and explicit session
reset. The supplied character and corner PNGs are unchanged copies of artwork
already published in this repository. See docs/ARTWORK_PROVENANCE.json
at the repository root for provenance; no new reuse license is granted.

## Run and stage

Use system Python with GTK 3, python3-gi, python3-cairo, python3-gi-cairo and the
GtkLayerShell introspection namespace in an active layer-shell Wayland session.
There is no normal-window fallback. A qualified Omega conversation runner and its
native/model closure are separate dependencies, not included in this directory.

```sh
/usr/bin/python3 app/companion.py --check
/usr/bin/python3 app/companion.py \
  --conversation-python /absolute/path/to/qualified/python \
  --conversation-runner /absolute/path/to/conversation/fresh_server.py
python3 stage.py /absolute/path/to/new-overlay
python3 -m unittest discover -s tests -v
```

The staging tool refuses an existing destination and creates an **uninstalled**
overlay with application and XDG autostart entries. It never activates autostart.
The installed launcher accepts ROKO_GUI_PYTHON, ROKO_CONVERSATION_PYTHON and
ROKO_CONVERSATION_RUNNER. A fresh-host Omega runner additionally uses the target
machine's independently qualified ROKO_FRESH_PROFILE. Do not reuse another
machine's inventory or turn a missing-runtime check into a fabricated reply.

## Transport contract

One backend process owns one in-memory conversation. Each request is a single
JSON line: `{"text":"ordinary free text","context":[]}`. A reply has exactly
`text`, `context_ids` (empty list) and integer `executed_actions: 0`. User/model
text is not evaluated as a command. The GUI remains responsive during inference.
The transport bounds text, wire output, diagnostics and per-turn duration.

Dismissal cancels a pending turn and invalidates late callbacks. A failed or
cancelled worker requires **New conversation** before another turn: no automatic
replay of possibly committed input. Backend-specific limits still apply; the
qualified fresh-host backend permits four exchanges and empty context only.
There is no durable-memory or full autonomous-agent claim.

## Verification and limits

29 companion tests and 3 preflight tests passed. Native tests on GTK 3.24.49,
gtk-layer-shell 0.9.0 and headless Sway 1.10.1/wlroots 0.18.2 verified avatar
startup, click-to-open, focused Enter submission, cancellation/reset, dismissal,
transparent-area click-through and keyboard focus on an ordinary background app.
A separately rebuilt actual Omega/PeTTa/Granite runtime passed a two-turn probe.
The visible bubble independently received a generated lighthouse-story opening
and correctly recalled the setting in the same session (about 57 and 47 seconds).
These finite tests do not establish arbitrary response quality or performance.

**COSMIC guest integration has not been qualified for this revision.** The
optional tracker executable is intentionally excluded from public source scope;
`--perch-active` requires a separately built/reviewed COSMIC geometry tracker.
Experimental head-input mode also requires its exact bound helper and an explicitly
controlled single-window scene. Do not enable it on an uncontrolled desktop.
Layer-shell cannot guarantee arbitrary interleaving with individual windows or
icons. Current flight moves a whole serpentine sprite, not a skeletal dragon
body wrapped around arbitrary window edges. Scaling and multi-output integration
need native COSMIC tests. See the public validation summary for scope.
