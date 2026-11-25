# Before-image review

All twelve existing actual-player-camera `before/*_Lit.png` files were viewed.
These are visual observations, not claims about collision or completed fixes.

| View | Specific problem visible in the baseline |
|---|---|
| Entrance | Cat is nearly a solid black silhouette; the foreground wall's dithered cutaway overlaps its right edge. Long bare recess walls provide no localized welcoming light or distinct military detail. |
| Lobby | Armor is recognizable through metallic highlights, but the cat has little body-plane separation. The space reads as an empty passage rather than a staffed guard lobby. |
| LowerHall | Broad empty floor dominates. One bright area spills from the right while fixtures are not legible in this view. Wall rhythm is repeated shallow arches with little projected depth. |
| Exhibition | The user-rejected black horizontal slabs and repeated swords dominate the foreground. The candle's pale body/flame read well, but a narrow angled stone exhibit with distinct mixed weapon silhouettes is needed. |
| Warehouse | Wood backs of racks hide most equipment identity; arrangements read as similar brown partitions. Preserve those seven collision/LOS roles while making each furnishing visually distinguishable. |
| CentralCorridor | Floor and bare walls dominate; D1 bars are readable, but nothing visually explains their actuation or relationship to the objectives. |
| CatBypass | Left wall lamp is a strong near-white hotspot while the cat and right walls remain dark. Keep narrow passage undecorated and protect the cat's upper silhouette from wall shadows. |
| Altar | Existing statue remains prominent; the actual release mechanism is partly concealed by the foreground wall. The control console is an isolated black slab. New functional chains should be readable from this fixed camera rather than placed only above it. |
| UpperCorridor | Cat crosses a large abrupt shadow, and the long wall remains empty except for repetitive recesses. Repeated localized fixtures and restrained military accents can create progression toward the gate without filling the path. |
| GateHall | A plain dark rectangular runner dominates; the huge near-right pillar crops much of the frame. Decorative floor hierarchy needs to work in the camera-visible lower part, not only near the offscreen gate arch. |
| GateHallExit | Cat blends strongly into the dark carpet directly in front of the final leaves. Door metalwork is nearly black while pillar faces carry most light. A restrained floor/door-side light should improve silhouette and make the final exit the focal point. |
| Weight1 | The old plate reads as a dark flat tray with no convincing docking function. Banner is visible, but surrounding floor/wall styling does not explain the mechanism connection. |

The large orange triangular overlays visible in Exhibition/Warehouse/GateHall
align with candle enemy sight indicators. Treat them as gameplay presentation,
not evidence that ambient lighting is orange, and preserve their logic.

Across all twelve views the floor texture is visible but architectural planes
feel broadly similar. Do not correct that by erasing stone detail or uniformly
raising exposure. Evaluate modeled depth and directional/local illumination in
DetailLighting, then verify the approved relative BaseColor values independently.
