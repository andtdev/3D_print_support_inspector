// A second test piece: a roof on two pillars, with three small tips hanging down from it.
// The roof needs supports and gets them. Each tip starts in mid-air, a few layers below the roof,
// flush with the roof's front face so it can be seen from the side.
// A low block of the model lies under the middle tip: with "On build plate only", the supports
// may not stand on it, so that tip gets none.

roof = [40, 12, 2];    // mm
height = 14;           // mm, the roof's underside above the bed
pillar = 6;            // mm
tips = [1.6, 2.4, 3.6];  // mm, the side of each square tip
tip_drop = 3;          // mm a tip hangs below the roof
block = [5, 12, 2];    // mm, the block under the middle tip

cube([pillar, roof.y, height]);
translate([roof.x - pillar, 0, 0]) cube([pillar, roof.y, height]);
translate([0, 0, height]) cube(roof);
for (i = [0 : len(tips) - 1])
    translate([pillar + (i + 1) * (roof.x - 2 * pillar) / (len(tips) + 1) - tips[i] / 2, 0, height - tip_drop])
        cube([tips[i], tips[i], tip_drop]);
translate([roof.x / 2 - block.x / 2, 0, 0]) cube(block);
