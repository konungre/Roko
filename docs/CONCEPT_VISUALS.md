# Roko concept gallery

These are AI-generated product illustrations, not runtime screenshots. They
depict a design direction for Roko on a COSMIC-inspired Linux desktop. They are
not official COSMIC artwork or an endorsement by System76. The desktop chrome
and notes content are illustrative, not a pixel-accurate implementation.

## Provenance and rights

The project owner requested this public README gallery. The character reference
was the owner's selected, previously generated emerald/gold Roko illustration.
The two new screens were made with built-in image generation, using that
reference for the first screen and the first screen for the second. No stock
photography, third-party screenshots, copied icon packs, private desktop
captures, account details, or real conversations were used. The original
reference and existing repository artwork were not modified or republished by
this change. No new project-wide or artwork reuse license is granted.

- `media/roko-desktop-concept.png`: an imagined quiet workspace, standing
  basilisk, organic chat bubble and input anchored to the character.
- `media/roko-flight-concept.png`: a second imagined state, with wingless flight
  and an attached smaller speech bubble.
- `media/roko-concept-storyboard.gif`: a two-frame, five-second looping
  storyboard made from those screens, reduced to 1000 pixels wide. It does not
  show continuous flight, interpolation, or the actual application running.

Every screen, including both GIF frames, carries the visible label
`CONCEPT MOCKUP · NOT A RUNNING BUILD`. Text in the mockup, including “Private
by design,” describes an aspiration, not an audited privacy or security claim.
No new runtime functionality or native integration is introduced by this gallery.

## Generation brief

First screen: preserve the emerald quadruped basilisk, gold-edged leafy crest,
gold belly and spiral tail. Show a dark emerald/charcoal COSMIC-inspired desktop,
gold light arcs, top panel, centered dock and a notes window. Put the character
directly on the desktop with an organic anchored bubble reading “What shall we
work on?” and “Ask Roko...”. Clearly label it as a concept, not a running build.

Second screen: preserve the same desktop and character identity, changing the
pose to graceful wingless flight with four limbs, a sweeping tail and subtle
gold motion trail. Keep the smaller bubble attached and reading “Right here
with you.” Retain the concept label and avoid private data.

## GIF reproduction

With ImageMagick installed, run from the repository root:

```sh
convert -delay 250 docs/media/roko-desktop-concept.png \
  docs/media/roko-flight-concept.png -resize 1000x -loop 0 \
  docs/media/roko-concept-storyboard.gif
```

The committed PNGs are the source of truth; generative images are not promised
to reproduce byte-for-byte from a prompt. `CONCEPT_VISUALS.json` records the
published files' dimensions, sizes and SHA-256 hashes. This is a supplemental
gallery, outside the historical initial `PUBLICATION_MANIFEST.json`.

## Screen-recording-style simulations and task mockups

The README now uses two continuous simulated desktop interactions instead of
the earlier two-frame storyboard. The original storyboard and both original
screens are preserved unchanged. Neither new GIF is runtime footage.

- `media/roko-task-demo.gif`: 14 seconds at approximately 12 fps. The cursor
  focuses the input, a request is typed, a checklist is proposed, the user
  applies it, and then checks the first item.
- `media/roko-autonomous-demo.gif`: 12 seconds at approximately 12 fps. Roko
  chooses to improve its explanations, reviews examples, drafts a shorter hint,
  and saves a local help card. This is fictional self-directed activity with
  no live model, real user input, external communication or purchase.
- Matching `*-still.png` files provide non-animated alternatives.
- Coding, shopping and research PNGs show additional aspirational assistance.
  Shopping products and prices are illustrative, not live offers. Research
  mockups outline a workflow and do not invent citations or factual findings.

The new screens are authored SVG desktop mockups rendered with Sharp. Their
character uses the existing, provenance-checked generated Roko sprite sheet
without modifying it. No new third-party art or private desktop captures were
used. Permanent labels identify the simulations and concepts in every frame.

### Reproduce the new media

With Node.js, Sharp and FFmpeg already installed, run from the repository root:

```sh
ROKO_FRAME_DIR=/tmp/roko-task-frames ROKO_AUTO_DIR=/tmp/roko-auto-frames \
  node docs/demo-source/render-demo.cjs
ffmpeg -framerate 12 -i /tmp/roko-task-frames/%04d.png \
  -vf 'split[a][b];[a]palettegen=max_colors=192[p];[b][p]paletteuse=dither=bayer:bayer_scale=3' \
  -loop 0 docs/media/roko-task-demo.gif
ffmpeg -framerate 12 -i /tmp/roko-auto-frames/%04d.png \
  -vf 'split[a][b];[a]palettegen=max_colors=192[p];[b][p]paletteuse=dither=bayer:bayer_scale=3' \
  -loop 0 docs/media/roko-autonomous-demo.gif
```

Output depends on the installed fonts, renderer and encoder versions. The
manifest hashes identify the reviewed published bytes, not a cross-platform
bit-for-bit reproducibility promise.

## Unified desktop and dynamic interaction revision

The README now selects the `*-v2` media. All earlier media and rendering source
remain preserved unchanged, including the original two generated hero screens.
The revised assets reuse a clean background plate made by editing the first
hero image with built-in image generation: remove its character, speech bubble
and window content while preserving the wallpaper, gold arcs, top panel, dock
and window placement. New four-pose transparent character art was generated
from that same hero reference. Both inputs are in `demo-source/assets/`.

The new code overlays a detailed IDE or browser in the original window area.
The IDE includes menus, explorer, tabs, numbered code, proposed changes and a
terminal. The browser includes tabs, navigation controls, address bar, bookmarks
and article/product content. These are authored app-like mockups, not screenshots
of real apps or endorsements by app vendors. Browser URLs use example.org;
content, products, prices, test commands and test results are fictional.

- `roko-task-demo-v2.gif`: 16 seconds, 192 frames at approximately 12 fps. Roko
  moves from the desktop into an IDE, highlights a patch, waits for a simulated
  user click, then moves to the terminal to inspect the illustrative result.
- `roko-autonomous-demo-v2.gif`: 14 seconds, 168 frames. Roko starts at the dock,
  flies to a browser, reaches toward Save and carries a source-link card into
  a local reading-list note. This is a self-chosen fictional goal, not live
  autonomous browsing or factual research.
- Coding, shopping and research `*-concept-v2.png` screens show Roko interacting
  with application content rather than standing in a fixed side position.
- The speech-bubble tails remain anchored to the moving character. Permanent
  concept and simulation labels remain visible in every frame.

No code, model, browser navigation, test command, purchase or external message
shown in these images actually executes. The source renders fictional frames.
No added image grants a new reuse license. No private captures or copied
third-party screenshots are included.

To reproduce the revised media with Node.js, Sharp and FFmpeg installed:

```sh
ROKO_FRAME_DIR=/tmp/roko-dynamic-task ROKO_AUTO_DIR=/tmp/roko-dynamic-auto \
  node docs/demo-source/render-dynamic-demo.cjs
ffmpeg -framerate 12 -i /tmp/roko-dynamic-task/%04d.png \
  -vf 'split[a][b];[a]palettegen=max_colors=224[p];[b][p]paletteuse=dither=bayer:bayer_scale=4' \
  -loop 0 docs/media/roko-task-demo-v2.gif
ffmpeg -framerate 12 -i /tmp/roko-dynamic-auto/%04d.png \
  -vf 'split[a][b];[a]palettegen=max_colors=224[p];[b][p]paletteuse=dither=bayer:bayer_scale=4' \
  -loop 0 docs/media/roko-autonomous-demo-v2.gif
```

Generation brief for the plate: preserve the exact emerald/gold desktop,
top panel, dock, concept badge and window chrome, removing only character,
bubble and content for reuse. Generation brief for the poses: preserve the
hero's green/gold quadruped basilisk identity in four isolated transparent
poses, standing, wingless flight, reaching and perching. The source assets,
not prompts alone, are the reproducible inputs to the frame renderer.
