# Visuals/dressing review

Reviewed against installed UE 5.8 source and actual prior imported mesh bounds.
No edits to the author's scripts were made by QA.

## Actionable findings sent to the director

1. **Runtime enum error, director reports fixed:** Python uses
   `CollisionResponseType.ECR_IGNORE`, not `CollisionResponse.ECR_IGNORE`.
   EngineTypes.h explicitly sets `ScriptName="CollisionResponseType"`.
2. **Warehouse north-opening interference:** Maintenance furniture at
   `(1030,1410)` occupies X942.5..1117.5, Y1372.5..1447.5 cm immediately below the
   original X900..1200 north opening. Remaining horizontal gaps are 42.5 and
   82.5 cm before character margins. Move it against the solid wall west of
   X900 (proposed center X760,Y1410) and verify actual traversal/LOS. The other
   five new furniture placements are wallside by measured mesh AABBs and do not
   intersect either straight puzzle push centerline. This is not a substitute
   for PIE traversal.
3. **One-centimetre exhibit base gap:** Pillar_Base is 25 cm high. Its Z scale
   .36 gives 9 cm while wedge bottom is 10 cm. Z scale .4 joins them exactly.
4. **Geometry conversion outcome:** Check the returned Outcome from
   `copy_mesh_to_static_mesh` before saving the wedge, then inspect resulting
   bounds. Existing asset reuse should not turn a failed partial creation into
   accepted geometry.
5. **Dock state presentation:** Approach fork/pin/chain are static separate
   actors in the reviewed version. The plate follows native 2 cm travel, but
   fork/pin do not automatically move to the provided latched state. This is a
   presentation gap, not a request to modify gameplay Source. Report it if no
   Stage3-only presentation response is implemented.

## Confirmed valid

- Separate attached weight/plate/bolt visual actors preserve native own-component
  bounds. Existing colliders and references remain the mechanical authority.
- Wedge top `Z=79+0.46Y` and weapon roll −65 degrees agree geometrically.
- Imported wall pilaster/sconce positive-Y projection agrees with dressing's
  mount yaws and flame offsets.
- Gate axis and border transformed spans align after yaw90: axis X−325..−75,
  left border−350..−325, right border−75..−50.

## Corrected preliminary concern: dock orientation

QA initially inferred that the rear should face +worldY from the push direction.
That inference was incomplete and is **withdrawn** after reading the source
README, Dock/README, `existing_plate_neighbors.json`, and `dock_traversal.json`.

The source explicitly prescribes **rear world−Y** for both docks. At P2, +Y posts
occupy Y2506..2536 and intersect the north wall Y2520..2550. Rear−Y provides a
65 cm east-side gap. P1's right 25 cm gap is explicitly not a cat route; its left
159 cm bypass is the intended circulation. Source mesh sweeps report no hits
for 20 X/Y axis/offset and weight/cat-envelope cases. Preserve the rear−Y
contract and verify imported per-part axes and the actual P1 left bypass in PIE.

The new furniture is explicitly authorized. QA therefore permits the six named
new solid furniture actors and reports them for required traversal/LOS checks;
it does not require large walkable furniture to be ghost geometry. New mechanism
skins and wall ornaments remain nonblocking.
