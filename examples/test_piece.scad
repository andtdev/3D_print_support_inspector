// A small part with one of everything the inspector looks for. Sliced without supports it has a hanging
// ledge, a long bridge and a steep wall; a short bridge and a 40 degree wall are fine.
$fn = 48;
cube([44, 18, 1.6]);                                   // base
translate([0, 0, 0]) cube([6, 16, 14]);                // tower
translate([6, 2, 9]) cube([9, 12, 2]);                 // ledge: hangs, held on one side only
// long bridge between two posts, 16 mm span
for (x = [20, 40]) translate([x, 0, 0]) cube([4, 7, 9]);
translate([20, 0, 9]) cube([24, 7, 1.6]);
// short bridge, 4 mm span
for (x = [20, 28]) translate([x, 9, 0]) cube([4, 7, 6]);
translate([20, 9, 6]) cube([12, 7, 1.6]);
// walls leaning out: 40 degrees from vertical (fine) and 65 degrees (steep)
translate([36, 9, 0]) rotate([90, 0, 90]) linear_extrude(3) polygon([[0, 0], [3, 0], [3 + 6 * tan(40), 6], [6 * tan(40), 6]]);
translate([41, 9, 0]) rotate([90, 0, 90]) linear_extrude(3) polygon([[0, 0], [2, 0], [2 + 2.4 * tan(65), 2.4], [2.4 * tan(65), 2.4]]);
