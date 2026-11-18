# Frontend Direction

## Reference read

The reference image is not a dashboard. It is an isometric neighborhood with:
- warm, painted textures
- dense but readable building clusters
- clear road and block structure
- visual variation without visual noise

That means the product should lead with a navigable colony scene, not a grid of cards.

## Current implementation

The frontend now uses:
- anchored scene markers on the colony image
- visible callout labels with explicit persona names
- SVG connector lines between labels and the mapped building cluster
- a right-side navigator for quick persona access
- modal impact windows for the real detail state
- a mobile label rail when the overlay would become too dense

## Scene structure

The first interactive colony should expose 7 entities:
- `lig_households`
- `mig_households`
- `hig_households`
- `farmers`
- `msmes`
- `public_services`
- `market_activity`

Each entity maps to a visible cluster or landmark so the scene does not depend on tiny hitboxes.

## Interaction model

Use click for the real detail state:
- highlight the selected cluster
- open a dedicated impact window, not a passive side panel
- show persona metrics plus a filtered set of macro metrics relevant to that persona
- keep the grounded summary action inside the window
- keep labels readable without needing hover first

Do not put critical information inside floating tooltip-only UI. That breaks on touch devices and becomes unreadable in a dense isometric layout.

## Visual rules

- Keep the palette earthy and civic, not neon.
- Use building form to imply socioeconomic difference. Do not rely only on labels.
- Roads, trees, water lines, and public spaces should help separate interaction zones.
- Reserve animation for state changes: selection, loading, and data refresh.
- Keep charts and dense metrics outside the map surface. Put them in the modal window, side navigator, or bottom rail.

## Asset implications

The scene will need:
- 3 residential archetypes
- 1 agricultural zone
- 1 MSME or workshop cluster
- 1 public-service building
- 1 market/commercial strip
- ambient assets: trees, footpaths, roads, utilities

## Technical direction in repo

The shipped frontend uses:
- static HTML
- absolute-positioned DOM overlays for markers and labels
- SVG for connector lines
- modal windows for detailed persona effects

That is the right choice for the current scope because:
- entity count is still small
- the scene is one fixed reference image
- DOM positioning is easier to tune than a premature canvas rewrite

Move to `canvas` only if:
- the scene becomes large
- entity count grows beyond simple overlay management
- animation density starts hurting performance

## API-facing shape

Each entity should eventually receive:
- baseline metrics
- simulated metrics
- delta values
- narrative summary

The supporting entity definitions are stored in [configs/colony_entities.json](/home/srao/Downloads/Eco_Sim/configs/colony_entities.json).
