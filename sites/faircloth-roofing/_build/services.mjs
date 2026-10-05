// One entry per service page. Each becomes services/<slug>/index.html.
// Copy is written per service on purpose: pages that only swap a keyword or a
// town name are thin content to search engines. Inline HTML is allowed in the
// text fields (this file is trusted); prices are demo ranges.
export const services = [
  {
    slug: 'roofing',
    name: 'Roofing',
    title: 'Roof Replacement & Repair in Fayetteville, NC',
    description: 'Roof replacement, repair and storm claims in Fayetteville, NC and towns within 50 miles. Shingle, metal and flat roofs, free inspections, written warranties.',
    serviceType: 'Roofing',
    kicker: 'Fayetteville, NC · Roofing',
    h1: 'Roof replacement &amp; repair in <span>Fayetteville</span>',
    sub: 'Tear-offs, leak repairs and storm claims for homes and businesses across Cumberland County and the Sandhills. Most replacements are done in one to two days.',
    image: { src: 'img/bundles-on-roof.jpg', alt: 'Bundles of new shingles staged along the ridge of a house', w: 1000, h: 664,
      credit: ['Shingles atop roof', 'Joe Mabel', 'CC BY 4.0', 'https://commons.wikimedia.org/wiki/File:Shingles_atop_roof.jpg'] },
    intro: [
      'A roof in Fayetteville has a hard job. Summers bake shingles past 150°F, afternoon thunderstorms dump an inch of rain in half an hour, and every few years a hurricane or its leftovers comes through with wind that finds every weak spot. Builder-grade shingles that would last 25 years further north often start curling and shedding granules here by year 15 to 18.',
      'We replace and repair every common roof type in the area, from architectural shingles on a Haymount bungalow to standing-seam metal on a Hope Mills farmhouse to TPO on a Skibo Road storefront. Every job starts with a free inspection and a written report with photos, so you can see what we see before you spend anything.'
    ],
    includedTitle: 'Every full replacement includes',
    included: [
      ['Full tear-off to the deck.', 'We never lay new shingles over old ones. It hides rot and voids most manufacturer warranties.'],
      ['Decking inspection and repair.', 'Soft or delaminated plywood is replaced at a per-sheet price we quote before work starts.'],
      ['Synthetic underlayment and ice &amp; water shield', 'in valleys, around chimneys and at every wall-to-roof joint.'],
      ['New flashing, pipe boots and drip edge.', 'Reusing old flashing is the number one cause of leaks on new roofs.'],
      ['Balanced ventilation.', 'Ridge and soffit vents sized to your attic, which keeps shingles cooler and your upstairs more comfortable.'],
      ['Magnetic sweep and cleanup.', 'Tarps over shrubs during tear-off, and the yard and driveway swept for nails twice.']
    ],
    options: {
      title: 'Roofing options we install',
      note: 'Installed price per square (100 sq ft of roof) including tear-off. Demo ranges for illustration; your inspection sets a firm price.',
      rows: [
        ['Architectural asphalt shingle', 'The most common choice here. Thick, dimensional look, 110–130 mph wind ratings with the right nailing pattern.', '25–30 yr', '$570–$850'],
        ['3-tab asphalt shingle', 'Lowest cost. Flat look, lower wind rating. Best for rentals or a short ownership horizon.', '15–20 yr', '$470–$670'],
        ['Standing-seam metal', 'Concealed fasteners, sheds rain fast, handles hurricane gusts. Reflective finishes cut attic heat.', '40–70 yr', '$1,190–$1,750'],
        ['Exposed-fastener metal', 'R-panel and 5V crimp for farmhouses, barns and shops. Screws need re-tightening every 10–15 years.', '25–40 yr', '$740–$1,100'],
        ['Synthetic slate', 'Slate look at a fraction of the weight. Class 4 impact ratings available.', '40–50 yr', '$1,090–$1,650'],
        ['TPO / EPDM flat roof', 'Single-ply membranes for low-slope porches, additions and commercial buildings.', '20–30 yr', '$740–$1,150']
      ]
    },
    signsTitle: 'Signs your roof needs work',
    signs: [
      ['Granules collecting at the downspouts.', 'Once the protective granules wash off, UV breaks down the asphalt quickly.'],
      ['Curled, cupped or cracked shingles,', 'usually first on the south- and west-facing slopes that take the afternoon sun.'],
      ['Dark streaks or green growth.', 'Algae and moss hold moisture against the shingles. Streaks alone are cosmetic, but moss lifts tabs.'],
      ['Water stains on ceilings or attic sheathing.', 'Water runs along rafters, so the source is often several feet uphill from the stain.'],
      ['Daylight through the attic boards', 'or a deck that feels spongy underfoot.']
    ],
    steps: [
      ['Free inspection', 'We go on the roof and into the attic, take photos of everything, and walk you through them on your phone or ours.'],
      ['Written quote', 'Line-item pricing for materials, labor, decking per sheet and any extras. No pressure, and the quote holds for 30 days.'],
      ['Pick your system', 'Shingle line, color, ventilation and any upgrades. We bring physical samples so you can see them against your brick or siding.'],
      ['Build day', 'Crew arrives around 7am. Tear-off, deck repairs, underlayment, flashing and shingles, usually finished the same day.'],
      ['Walkthrough &amp; warranty', 'Final inspection with you, nail sweep, photos of the finished roof, and your manufacturer warranty registered.']
    ],
    local: {
      title: 'Built for Sandhills weather',
      paras: [
        'Cumberland County sits in a wind zone where building code expects roofs to hold against roughly 120 mph gusts. We nail every shingle with six nails instead of four and seal starter strips on rakes and eaves, which is what manufacturers require for their high-wind warranties.',
        'Hurricanes Matthew (2016) and Florence (2018) both dropped more than a foot of rain on parts of the region. The roofs that leaked were rarely missing shingles. They leaked at flashing, pipe boots and valleys. That is why we replace all of it on every job, not just the field shingles.'
      ]
    },
    faq: [
      ['How much does a new roof cost in Fayetteville?', 'Most single-family homes in the area fall between $9,000 and $18,000 for architectural shingles, depending on size, steepness, layers to remove and decking repairs. Metal runs roughly two times that. The instant estimator on our home page gives you a ballpark in about 20 seconds. <span class="demo">demo</span>'],
      ['Can you repair my roof instead of replacing it?', 'Often, yes. If the shingles are under about 15 years old and the problem is a flashing failure, a cracked pipe boot or storm damage to one slope, a repair is the right call and we will tell you so.'],
      ['Do I need a permit for a roof replacement?', 'In Fayetteville and unincorporated Cumberland County, a full replacement on a home typically needs a building permit. We pull it and schedule any required inspection as part of the job.'],
      ['Will insurance pay for my new roof?', 'If the damage came from wind, hail or a fallen tree, often yes. Age and wear usually are not covered. We document storm damage with photos and meet your adjuster on the roof.'],
      ['How long will the crew be at my house?', 'One to two days for most homes. Steep, cut-up or multi-layer roofs and metal installs can take three to five.']
    ],
    related: ['gutters', 'siding']
  },

  {
    slug: 'gutters',
    name: 'Gutters',
    title: 'Seamless Gutters & Gutter Guards in Fayetteville, NC',
    description: 'Seamless aluminum gutters, downspouts and leaf guards in Fayetteville, NC. 5" and 6" K-style and half-round, formed on site to fit your house. Free estimates.',
    serviceType: 'Gutter installation',
    kicker: 'Fayetteville, NC · Gutters',
    h1: 'Seamless gutters built for <span>Carolina downpours</span>',
    sub: 'Five- and six-inch seamless aluminum gutters formed on site, with downspouts sized for summer storms and guards that keep pine straw out.',
    image: { src: 'img/gutters.jpg', alt: 'Aluminum gutter and downspout along the edge of a roof', w: 1000, h: 667,
      credit: ['Commercial Box Gutter', 'Ethoseo', 'CC BY 3.0', 'https://commons.wikimedia.org/wiki/File:Commercial_Box_Gutter.jpeg'] },
    intro: [
      'Gutters are the cheapest part of protecting a house from water, and the part most often done wrong. Undersized troughs overflow in a July thunderstorm, sectional joints drip within a few years, and downspouts that dump next to the foundation wash out the sandy soil around much of Fayetteville and send water into crawlspaces.',
      'We roll seamless gutters from a coil on our truck, cut to the exact length of each run, so the only joints are at the corners. Every install includes new downspouts, hidden hangers and a plan for where the water goes once it reaches the ground.'
    ],
    includedTitle: 'Every gutter install includes',
    included: [
      ['Seamless runs formed on site.', 'One continuous piece per wall, with sealed and riveted corners.'],
      ['Hidden hangers every 24 inches,', 'screwed into the fascia rafter tails so the gutter holds under a full load of water and wet leaves.'],
      ['Correct pitch.', 'About a quarter inch of fall per 10 feet, so water drains instead of standing and breeding mosquitoes.'],
      ['Downspouts sized and placed for your roof.', '3×4" oversize downspouts where a big roof plane drains to one corner.'],
      ['Splash blocks or extensions', 'that move water at least four feet from the foundation, or tie-ins to underground drains.'],
      ['Fascia check.', 'We replace soft fascia boards before hanging new gutters on them.']
    ],
    options: {
      title: 'Gutter options',
      note: 'Installed price per linear foot. Demo ranges for illustration; your estimate sets a firm price.',
      rows: [
        ['5" K-style aluminum', 'Standard on most homes. Handles typical roof areas and pitches.', '20–30 yr', '$9–$13 / ft'],
        ['6" K-style aluminum', '40% more capacity. Our pick for steep roofs, long runs and valleys that funnel water to one spot.', '20–30 yr', '$11–$16 / ft'],
        ['Half-round aluminum or copper', 'Traditional profile for historic and custom homes. Copper ages to a brown patina.', '25–50+ yr', '$16–$40 / ft'],
        ['Micro-mesh gutter guards', 'Stainless mesh that blocks pine needles and roof grit while letting heavy rain through.', '20+ yr', '$8–$14 / ft'],
        ['Screen or reverse-curve guards', 'Lower cost. Good for broad-leaf trees, less effective against pine straw.', '10–15 yr', '$4–$8 / ft'],
        ['Underground downspout drains', 'Buried pipe that carries water to a pop-up emitter away from the house.', '30+ yr', '$15–$30 / ft']
      ]
    },
    signsTitle: 'Signs your gutters are failing',
    signs: [
      ['Water spilling over the front edge in heavy rain,', 'even when the gutter is clean. That means it is undersized or pitched wrong.'],
      ['Drips at seams and corners,', 'or rust streaks and peeling paint on the fascia behind the gutter.'],
      ['Sagging runs or hangers pulling out', 'of the fascia, often after a load of wet leaves or ice.'],
      ['Washed-out mulch or bare trenches', 'in the beds below the roof edge, or standing water against the foundation.'],
      ['A damp or musty crawlspace', 'after storms. Many of those trace back to downspouts emptying beside the house.']
    ],
    steps: [
      ['Measure &amp; plan', 'We measure every run, look at roof size and pitch above each one, and decide where each downspout should drain.'],
      ['Written estimate', 'Price per foot, downspouts, guards and any fascia repair listed separately. Usually the same day.'],
      ['Remove old gutters', 'Old gutters come down and are hauled off. We repair or replace fascia that has rotted behind them.'],
      ['Form &amp; hang', 'Gutters are rolled from coil on site in your trim color, then hung on hidden hangers with the right pitch.'],
      ['Water test', 'We run a hose through every run before we leave to confirm it drains to the downspouts with no leaks.']
    ],
    local: {
      title: 'Pine straw, sand and summer storms',
      paras: [
        'Longleaf and loblolly pines are everywhere around Fayetteville, and their needles mat into a dam that most screen guards let right through. On homes under pines we recommend stainless micro-mesh, which is the one guard type that reliably keeps needles out without blocking heavy rain.',
        'Much of the area sits on sandy Sandhills soil that drains fast but erodes easily. A downspout that dumps beside the foundation can undercut a slab or flood a crawlspace in a single summer, so every install ends with water moved well away from the house.'
      ]
    },
    faq: [
      ['How much do new gutters cost?', 'For a typical one-story Fayetteville home with about 150 feet of gutter, seamless 5" aluminum with downspouts usually runs $1,400 to $2,200. Six-inch gutters and guards add to that. <span class="demo">demo</span>'],
      ['5-inch or 6-inch gutters?', 'Five-inch handles most single-story homes. We recommend 6-inch for steep roofs, large roof areas draining to one run, and anywhere a valley dumps water into the gutter.'],
      ['Are gutter guards worth it?', 'Under pine trees, yes. Micro-mesh guards cut cleanings from two or three a year to an occasional rinse. Under a few hardwoods with an easy roofline, regular cleaning may be cheaper.'],
      ['Can you match my trim color?', 'Yes. Seamless aluminum comes in dozens of factory colors, and we bring a color chart to the estimate.'],
      ['Do you replace gutters during a roof replacement?', 'We can, and it is the cheapest time to do it because the drip edge and fascia are already exposed. If your gutters are in good shape, we protect and reuse them.']
    ],
    related: ['roofing', 'siding']
  },

  {
    slug: 'siding',
    name: 'Siding',
    title: 'Siding Installation & Repair in Fayetteville, NC',
    description: 'Vinyl and fiber cement siding installation, replacement and storm repair in Fayetteville, NC. House wrap, trim and soffit included. Free inspections.',
    serviceType: 'Siding installation',
    kicker: 'Fayetteville, NC · Siding',
    h1: 'Siding installation &amp; repair in <span>Fayetteville</span>',
    sub: 'Vinyl, fiber cement and engineered wood siding, plus soffit, fascia and trim. Full replacements, storm repairs and color matching for one damaged wall.',
    image: { src: 'img/siding.jpg', alt: 'A two-story building clad in white vinyl lap siding under storm clouds', w: 1400, h: 949,
      credit: ['Vinyl siding covered building, Buffalo, MN', 'Myotus', 'CC BY 4.0', 'https://commons.wikimedia.org/wiki/File:Vinyl_siding_covered_building,_Buffalo,_MN.jpg'] },
    intro: [
      'Siding is the other half of your home’s weather shell. When it cracks, warps or comes loose, rain gets behind it and soaks the sheathing and framing, and in our humidity that turns into rot and mold faster than most people expect. Hail and wind that damage a roof usually damage the siding on the same side of the house, too.',
      'We install and repair vinyl, fiber cement and engineered wood siding on homes across the Fayetteville area. Every replacement goes down to the sheathing, so we can fix soft spots and put on new house wrap and flashing before the new siding goes up.'
    ],
    includedTitle: 'Every siding replacement includes',
    included: [
      ['Full removal of the old siding', 'and a sheathing inspection, with rotten boards replaced at a price we quote up front.'],
      ['New weather-resistive barrier.', 'House wrap lapped and taped so water that gets behind the siding drains out instead of in.'],
      ['Flashing at every window, door and roof line.', 'Kick-out flashing where a roof meets a wall, which is where most hidden rot starts.'],
      ['New trim, corners and J-channel', 'in a matching or contrasting color.'],
      ['Soffit and fascia', 'wrapped or replaced so the eaves match the new walls and stay vented.'],
      ['Haul-off and cleanup', 'with a magnetic sweep around the whole house.']
    ],
    options: {
      title: 'Siding options',
      note: 'Installed price per square (100 sq ft of wall) including removal. Demo ranges for illustration; your inspection sets a firm price.',
      rows: [
        ['Standard vinyl', 'Low cost and low upkeep. Never needs paint. Can crack in hail or warp near a reflective window.', '20–30 yr', '$450–$750'],
        ['Insulated vinyl', 'Foam-backed panels that stand straighter, resist dents better and add some insulation.', '30–40 yr', '$700–$1,100'],
        ['Fiber cement (lap or shingle)', 'Cement board that resists fire, rot, termites and hail. Factory-painted finishes hold color 15+ years.', '30–50 yr', '$900–$1,400'],
        ['Engineered wood', 'Real wood look, lighter than fiber cement, treated against rot and termites.', '25–30 yr', '$750–$1,150'],
        ['Board &amp; batten', 'Vertical profile in vinyl or fiber cement, popular on farmhouse styles and accent gables.', '25–50 yr', '$700–$1,300'],
        ['Soffit &amp; fascia wrap', 'Vented vinyl or aluminum soffit and aluminum-wrapped fascia. No more painting eaves.', '25–40 yr', '$12–$24 / ft']
      ]
    },
    signsTitle: 'Signs your siding needs attention',
    signs: [
      ['Cracked, holed or missing panels,', 'often on the side of the house that faced the last hailstorm.'],
      ['Warped or buckled panels.', 'Vinyl nailed too tight cannot expand in summer heat and ripples off the wall.'],
      ['Soft spots when you press on the wall,', 'especially below windows and where a roof line meets the wall.'],
      ['Peeling paint or swelling', 'on wood or older hardboard siding, which means water is getting into the boards.'],
      ['Mold, mildew or wallpaper peeling inside', 'on an exterior wall, or rising cooling bills from drafts.']
    ],
    steps: [
      ['Free inspection', 'We check every wall, press-test the areas that rot first, and photograph any storm damage for insurance.'],
      ['Material &amp; color', 'We bring full-size samples so you can see colors and profiles against your roof, brick and trim in daylight.'],
      ['Written quote', 'Price per square, trim, soffit and fascia, and a per-sheet price for any sheathing repair, listed separately.'],
      ['Strip, repair, wrap', 'One or two walls at a time, so the house is never left open overnight. Sheathing fixed, wrap and flashing installed.'],
      ['Install &amp; walkthrough', 'Siding, trim and soffit go up, then a final walkthrough with you and a magnetic sweep around the yard.']
    ],
    local: {
      title: 'Heat, humidity and hail',
      paras: [
        'Fayetteville summers are hot and wet, which is hard on siding in two ways. Vinyl expands and contracts more than most people expect, so we hang it loose enough to move, the way manufacturers require. And the humidity means any water that gets behind the siding stays there, which is why we never skip the house wrap and flashing details.',
        'Spring hail is the most common reason we replace siding on newer homes. Hail that cracks vinyl on one side of the house usually means the roof took hits too, so we inspect both at once and document everything for a single insurance claim.'
      ]
    },
    faq: [
      ['How much does new siding cost in Fayetteville?', 'Most homes in the area run between $11,000 and $22,000 for vinyl, and roughly 1.5 to 2 times that for fiber cement, depending on wall area, stories and trim detail. <span class="demo">demo</span>'],
      ['Can you replace just the damaged panels?', 'Usually. For storm damage on one or two walls, we match the profile and color. If the original color has faded or been discontinued, we will show you the closest match before any work starts.'],
      ['Vinyl or fiber cement?', 'Vinyl costs less and never needs paint. Fiber cement costs more but stands up to hail, fire and termites, looks closer to painted wood, and adds more resale value. Under heavy tree cover or in hail-prone spots, fiber cement is worth a look.'],
      ['Does insurance cover hail-damaged siding?', 'Often, when the damage is from a covered storm. We photograph every crack and dent, write a line-item scope and meet the adjuster at the house.'],
      ['How long does a siding job take?', 'About three to seven days for a typical one- or two-story home, depending on size, trim detail and how much sheathing needs repair.']
    ],
    related: ['roofing', 'gutters']
  }
];
