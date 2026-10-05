#!/usr/bin/env python3
"""Builds the Faircloth Roofing service and town pages, and keeps the shared
header, footer, service cards and town list in index.html in sync.

Run from anywhere:  python3 sites/faircloth-roofing/_src/build.py
Edit content here (SERVICES, TOWNS), not in the generated HTML.
Jekyll skips folders that start with "_", so this folder is never published.
"""
import json
import math
import re
from html import escape
from pathlib import Path

SRC = Path(__file__).resolve().parent
SITE = SRC.parent
BASE_URL = "https://spenc13.github.io/sites/faircloth-roofing/"
PHONE, TEL = "(910) 555-0142", "tel:+19105550142"
HQ = (35.0527, -78.8784)

IMG = {
    "bundles-on-roof": (1000, 664), "crew-work": (1600, 1063), "flat-roof": (1000, 667),
    "gutters": (1000, 667), "hero-crew": (1920, 1285), "metal-seam": (1000, 750),
    "shingles-new": (1400, 933), "shingles-worn": (1400, 1050), "tarp-crew": (1000, 695),
    "tarp-damaged-roof": (1000, 665), "siding": (1400, 949),
}

# --------------------------------------------------------------------------- services
SERVICES = [
    dict(
        slug="roof-replacement", name="Roof replacement", nav="Shingle and slate roofs, tear-off to ridge",
        img="bundles-on-roof", alt="Bundles of new shingles staged along the ridge of a house", tag="Most requested",
        card="Full tear-off down to the deck, rotten boards replaced, new underlayment, flashing, vents and shingles. Most homes are done in one to two days.",
        chips=["Architectural shingle", "3-tab", "Synthetic slate"],
        h1='Roof <span>replacement</span>', need="Full replacement",
        title="Roof Replacement in Fayetteville, NC",
        desc="Full tear-off roof replacement in Fayetteville, NC and 50 miles around: architectural shingles, metal, synthetic slate. Free inspection and written scope.",
        sub="Tear-off to the deck, a complete system from one manufacturer, and a clean yard by dinner. Most homes take one to two days.",
        intro=[
            "A replacement is the biggest job a roof ever gets, so we treat it like one. We strip the old roof down to the deck, fix what's underneath, and build a complete system (underlayment, flashing, ventilation and shingles from one manufacturer) so the warranty covers all of it, not just the shingles.",
            "Before we start you get a written scope with the material, color, decking allowance and price. When we finish you get a photo report of the work you can't see from the ground.",
        ],
        included=[
            ("Full tear-off.", "Every old layer comes off so we can see and fix the deck."),
            ("Decking repair.", "Soft or rotten sheets are replaced at a per-sheet price agreed up front."),
            ("Underlayment and ice &amp; water shield.", "Synthetic felt everywhere, peel-and-stick in valleys and around every penetration."),
            ("New metal and flashing.", "Drip edge, step and counter flashing, pipe boots and chimney flashing."),
            ("Balanced ventilation.", "Ridge vent matched to soffit intake so the attic doesn't cook your shingles."),
            ("Cleanup and warranty.", "Magnet sweep of the yard and driveway, then we register your manufacturer warranty."),
        ],
        options_title="Pick the roof that fits your house",
        options=[
            ("Architectural shingle", "The default for most homes here: thick, dimensional, rated for high winds when installed to spec.", ["25–30 yr", "$480–$700 / sq demo"]),
            ("3-tab shingle", "The budget option. Flat look, lighter weight, and the shortest life. Good for rentals and outbuildings.", ["15–20 yr", "$380–$520 / sq demo"]),
            ("Standing-seam metal", "Costs more up front and lasts about twice as long. See our metal roofing page for the details.", ["40–70 yr", "$1,100–$1,600 / sq demo"]),
            ("Synthetic slate", "The look of slate at a fraction of the weight, so most houses need no extra framing.", ["40–50 yr", "$1,000–$1,500 / sq demo"]),
            ("Natural slate", "For historic homes and owners who never want to do this again. Needs a structure that can carry it.", ["75–100 yr", "$1,800–$3,000 / sq demo"]),
            ("Cedar shake &amp; tile", "Specialty roofs we repair and replace, including matching existing tile on additions.", ["25–50+ yr", "Quoted per job"]),
        ],
        steps=[
            ("Free inspection", "We measure the roof, check the attic and decking, and photograph what we find."),
            ("Written proposal", "Material, color, decking allowance, start date and one price. No pressure, no expiring deals."),
            ("Delivery", "Shingles arrive a day or two ahead. We tarp shrubs and protect AC units and pools."),
            ("Build day", "Tear-off, deck repair and dry-in happen the same day, so your house is never left open."),
            ("Walk-through", "We walk the finished roof and yard with you, then send the photo report and warranty."),
        ],
        signs_title="Signs it's time",
        signs=[
            ("Cracked, curling or missing shingles", "in more than a few spots."),
            ("Granules piling up in the gutters", "and bare, shiny patches on the roof."),
            ("Daylight or stains in the attic", "or a sagging section of roof deck."),
            ("A roof past 20 years", "especially original builder-grade 3-tab."),
        ],
        faqs=[
            ("Can you put new shingles over my old ones?", "Code allows a second layer in some cases, but we almost always recommend a tear-off. Overlays hide rotten decking, add weight, and many manufacturers won't give their best warranty on them."),
            ("Do I need to be home on build day?", "No. We need access to the driveway and an outside outlet. Most owners are home for the walk-through at the end."),
            ("What if it rains during the job?", "We only open as much roof as we can dry in that day, and we watch the radar. If a storm pops up, the crew tarps the open section before they leave."),
            ("Do you pull the permit?", "Yes. We pull the permit wherever your town or county requires one and schedule the inspection."),
        ],
    ),
    dict(
        slug="storm-damage-repair", name="Storm & hail repair", nav="Tarping, wind and hail, insurance claims",
        img="tarp-damaged-roof", alt="A worker tarping a wind-damaged shingle roof with missing shingles", tag="24/7",
        card="Wind-lifted shingles, hail bruising, limbs through the roof. We tarp it the same day and photograph every hit for your insurance claim.",
        chips=["Emergency tarping", "Hail inspections", "Insurance claims"],
        h1='Storm &amp; hail <span>repair</span>', need="Storm / hail damage",
        title="Storm Damage & Hail Roof Repair in Fayetteville, NC",
        desc="24/7 emergency tarping, wind and hail roof repair, and insurance claim help in Fayetteville, NC and every town within 50 miles. We meet your adjuster.",
        sub="Same-day tarping, a photo report for your insurer, and a roofer standing next to your adjuster on the roof.",
        intro=[
            "Hurricane season runs June through November here, and spring brings hail and straight-line wind. When a storm finds your roof, the first job is to stop the water. The second is to document every bit of damage before it gets missed or forgotten.",
            "We do both. A crew tarps the roof the same day when water is getting in, and an inspector photographs the roof, gutters, siding and attic so your claim has proof behind it.",
        ],
        included=[
            ("Emergency tarping.", "Answered 24/7 after storms. Stops further damage and meets your policy's duty to prevent further loss."),
            ("Full storm inspection.", "Roof, gutters, vents, siding, windows and attic, with dated photos of every hit."),
            ("Line-item scope.", "A report in the format adjusters use, so the estimate starts from the right quantities."),
            ("Adjuster meeting.", "We're on the roof with your adjuster and point out everything we found."),
            ("Supplements.", "If hidden damage turns up during the build, we document it and file the supplement."),
        ],
        options_title="What we fix after a storm",
        options=[
            ("Wind damage", "Creased, lifted or missing shingles, blown-off ridge cap, loose flashing and exposed nails.", ["Often covered", "Repair or replace"]),
            ("Hail damage", "Bruised shingles where granules are knocked off, dented vents, gutters and flashing.", ["Often covered", "Free hail check"]),
            ("Trees &amp; limbs", "Punctured decking and cracked rafters. We coordinate with your tree crew and frame the repair.", ["Often covered", "Same-day tarp"]),
            ("Hurricane damage", "Widespread wind damage plus driven-rain leaks. A separate hurricane deductible may apply.", ["Check deductible", "24/7 response"]),
        ],
        steps=[
            ("Call or text", "Tell us what happened. Active leaks go to the front of the line."),
            ("Tarp &amp; inspect", "We stop the water, then inspect and photograph everything."),
            ("You file, we document", "You open the claim with your insurer. We send you the photo report and scope to attach."),
            ("Adjuster meeting", "We meet the adjuster on the roof so nothing gets missed."),
            ("Build &amp; close-out", "Repair or replacement, final photos, and any supplements filed."),
        ],
        signs_title="Check these after a storm",
        signs=[
            ("Dents on gutters, downspouts and vents.", "If metal got hit, the shingles did too."),
            ("Shingles or ridge cap in the yard.", "Even one missing tab can let water in."),
            ("New ceiling stains or a musty attic.", "Wind-driven rain gets in under lifted shingles."),
            ("Limbs on or over the roof.", "Don't climb up. Call us and we'll check it safely."),
        ],
        faqs=[
            ("How soon after a storm should I call?", "As soon as it's safe. Many policies require prompt notice, and damage that sits gets harder to tie to a specific storm. A free inspection costs you nothing either way."),
            ("Do you work with my insurance company?", "Yes, with all the major carriers. You file the claim and stay in control of it. We provide documentation and meet the adjuster."),
            ("Will you ask me to sign over my claim?", "No. We never ask for an assignment of benefits, and you should be wary of anyone who does."),
            ("Is emergency tarping covered?", "Reasonable steps to prevent further damage are usually reimbursable under your policy. We give you an itemized invoice to submit with the claim."),
        ],
    ),
    dict(
        slug="metal-roofing", name="Metal roofing", nav="Standing seam and exposed-fastener panel",
        img="metal-seam", alt="A ranch house with a new standing-seam metal roof, seen from above", tag="40+ years",
        card="Standing-seam and screw-down panel for homes, farmhouses, barns and shops. Sheds heavy rain fast and holds up to hurricane gusts.",
        chips=["Standing seam", "R-panel &amp; 5V", "Metal retrofits"],
        h1='Metal <span>roofing</span>', need="Metal roof",
        title="Metal Roofing in Fayetteville, NC",
        desc="Standing-seam and exposed-fastener metal roofs for homes, farmhouses, barns and shops in Fayetteville, NC and 50 miles around. Built for hurricane winds.",
        sub="Standing seam for homes, R-panel and 5V for barns and shops. One roof that can outlast two or three shingle roofs.",
        intro=[
            "Metal costs more than shingles on day one and less over the life of the house. A standing-seam roof sheds a summer downpour in seconds, reflects heat, and holds its panels through gusts that peel shingles off the house next door.",
            "We install both concealed-fastener standing seam and exposed-fastener panel, on houses, farmhouses, barns, shops and carports, with trim bent to fit your roof.",
        ],
        included=[
            ("Panels in your color.", "Galvalume or painted steel in a range of stock colors, with matching trim."),
            ("High-temp underlayment.", "Rated for the heat that builds under metal in a Carolina summer."),
            ("Custom trim.", "Ridge, rake, eave, valley and flashing bent to fit, with closures to keep out wasps and wind-driven rain."),
            ("Fastening to spec.", "Clip and screw patterns that match the panel's published wind rating."),
            ("Two warranties.", "The manufacturer's paint and panel warranty, plus our workmanship warranty."),
        ],
        options_title="Panel types",
        options=[
            ("Standing seam", "Raised seams with hidden clips. Clean lines, no exposed screws, and room for the panel to expand in the heat.", ["40–70 yr", "$1,100–$1,600 / sq demo"]),
            ("R-panel / PBR", "Exposed-fastener panel for barns, shops and budget-minded homes. Strong and fast to install.", ["25–40 yr", "$650–$950 / sq demo"]),
            ("5V crimp", "The classic Southern farmhouse look. Exposed fastener, great on porches and older homes.", ["25–40 yr", "Quoted per job"]),
            ("Metal over shingles", "On the right house we can install metal over one layer of shingles with an underlayment and battens, skipping the tear-off.", ["Inspection required", "Saves disposal"]),
        ],
        steps=[
            ("Inspection &amp; measure", "We check the deck and framing and measure for panel lengths."),
            ("Color &amp; panel choice", "Samples on site so you see them against your brick and trim."),
            ("Fabrication", "Panels are cut to length and trim is bent for your roof."),
            ("Install", "Most homes take two to four days. Barns and shops depend on size."),
            ("Final check", "Every screw and seam inspected, scraps and shavings cleaned up."),
        ],
        signs_title="Metal makes sense when",
        signs=[
            ("You plan to stay ten years or more.", "That's when metal starts paying for itself."),
            ("Your roof gets hit by wind often.", "Open lots, farmland and tall pines all mean more wind."),
            ("The roof is low-slope or a porch.", "Standing seam handles slopes shingles can't."),
            ("It's a barn, shop or outbuilding.", "Panel roofs go on fast and need little upkeep."),
        ],
        faqs=[
            ("Is a metal roof loud in the rain?", "Not when it's installed over a solid deck with underlayment. Most people hear it about as much as shingles. Open-frame barns are louder."),
            ("Does metal attract lightning?", "No. Metal roofs aren't more likely to be struck, and they don't burn if they are."),
            ("Will hail dent it?", "Large hail can dent metal, usually cosmetically. Thicker gauges and textured finishes hide it better, and some panels carry impact ratings."),
            ("How long does the paint last?", "Quality painted panels carry long fade and chalk warranties from the manufacturer. We'll show you the terms for the color you pick."),
        ],
    ),
    dict(
        slug="commercial-roofing", name="Commercial flat roofs", nav="TPO, EPDM, PVC, coatings",
        img="flat-roof", alt="A finished flat roof covered in a seamless rubber membrane with metal edge trim", tag="Commercial",
        card="TPO, EPDM, PVC and modified bitumen for offices, warehouses, churches and retail. Repairs, coatings and full replacements.",
        chips=["TPO", "EPDM", "PVC", "Coatings"],
        h1='Commercial <span>roofing</span>', need="Commercial roof",
        title="Commercial Roofing in Fayetteville, NC",
        desc="TPO, EPDM, PVC, modified bitumen and roof coatings for offices, warehouses, churches and retail in Fayetteville, NC and 50 miles around.",
        sub="Flat and low-slope roofs for offices, warehouses, churches, schools and retail. Repair, restore or replace, scheduled around your business.",
        intro=[
            "A commercial roof problem is a business problem: wet inventory, closed rooms, unhappy tenants. We start with a survey that tells you honestly whether the roof needs a repair, a restoration coating, or a full replacement, and what each costs.",
            "Work is scheduled around your hours, and every section we open is dried in the same day.",
        ],
        included=[
            ("Roof survey.", "Core samples, a moisture check and photos so you know what's under the membrane."),
            ("Options with numbers.", "Repair, coating and replacement priced side by side."),
            ("Drainage fixes.", "Tapered insulation, crickets, scuppers and drains to get rid of ponding water."),
            ("Daily dry-in.", "Your building is watertight at the end of every work day."),
            ("Maintenance plans.", "Twice-a-year inspections and drain cleaning to protect the warranty."),
        ],
        options_title="Systems we install",
        options=[
            ("TPO single-ply", "White, heat-welded seams, reflects summer sun. The most common choice for new low-slope roofs.", ["20–30 yr", "$650–$1,000 / sq demo"]),
            ("EPDM rubber", "Proven black or white rubber membrane. Tough, flexible and easy to repair.", ["25–30 yr", "$550–$900 / sq demo"]),
            ("PVC single-ply", "Best for restaurants and roofs that see grease or chemicals.", ["20–30 yr", "$750–$1,200 / sq demo"]),
            ("Modified bitumen &amp; BUR", "Multi-layer asphalt systems that hold up to foot traffic.", ["15–30 yr", "$550–$950 / sq demo"]),
            ("Silicone &amp; acrylic coatings", "Restores a sound roof without a tear-off, often for half the cost of replacing it.", ["+10–15 yr", "$250–$450 / sq demo"]),
            ("Commercial metal", "Standing seam and structural panel for warehouses and steel buildings.", ["40+ yr", "$900–$1,500 / sq demo"]),
        ],
        steps=[
            ("Survey", "Cores, moisture readings and photos of the whole roof."),
            ("Options &amp; budget", "Repair, restore and replace priced side by side, with expected life for each."),
            ("Schedule", "Work planned around your hours, deliveries and tenants."),
            ("Install", "Sections opened and dried in daily, with a site supervisor on the roof."),
            ("Close-out", "Manufacturer inspection and NDL warranty registered where the system qualifies."),
        ],
        signs_title="Call us when you see",
        signs=[
            ("Ponding water", "still standing 48 hours after rain."),
            ("Blisters, splits or open seams", "in the membrane."),
            ("Ceiling tiles stained", "or replaced more than once."),
            ("Rising cooling bills", "from wet insulation under the roof."),
        ],
        faqs=[
            ("Can you work while we're open?", "Yes. Most commercial jobs are done with the building in use. We plan crane lifts, noise and odors around your schedule."),
            ("Should we coat or replace?", "If the survey shows the insulation is mostly dry and the membrane is sound, a coating can add 10 to 15 years. If it's saturated, a coating just seals the water in."),
            ("What's an NDL warranty?", "A no-dollar-limit warranty from the membrane manufacturer that covers materials and labor for 15 to 30 years, after the manufacturer inspects the install."),
            ("Do you offer maintenance plans?", "Yes. Two inspections a year plus after major storms, with drains cleared and small repairs made on the spot."),
        ],
    ),
    dict(
        slug="roof-repair", name="Leak repair & inspections", nav="Leak tracing, flashing, roof reports",
        img="shingles-worn", alt="Close-up of worn asphalt shingles with cracked, curling edges", tag="Free",
        card="We trace the water to the flashing, pipe boot or valley that's actually failing, then give you a written report with photos.",
        chips=["Leak tracing", "Flashing", "Real-estate reports"],
        h1='Leak repair &amp; <span>inspections</span>', need="Leak repair",
        title="Roof Leak Repair & Inspections in Fayetteville, NC",
        desc="Roof leak repair and free roof inspections in Fayetteville, NC and 50 miles around. We find the real source and fix it, with a written photo report.",
        sub="Most leaks don't need a new roof. They need someone who finds the one failed boot, valley or flashing and fixes it right.",
        intro=[
            "Water travels. A stain over the bedroom can start ten feet away at a cracked pipe boot or a lifted piece of step flashing. Patching the spot over the stain rarely fixes anything, so we trace the leak from the attic and the roof until we find where water actually gets in.",
            "Every inspection comes with a written report and photos, whether you need a repair, a replacement, or just peace of mind before you buy or sell.",
        ],
        included=[
            ("Leak tracing.", "From inside the attic and on the roof, with a hose test when we need one."),
            ("Pipe boots &amp; vents.", "Cracked rubber boots are the most common leak we fix."),
            ("Flashing repair.", "Step, counter, chimney and wall flashing reset or replaced."),
            ("Shingle repair.", "Missing or damaged shingles replaced and matched as closely as possible."),
            ("Photo report.", "What we found, what we fixed, and what to keep an eye on."),
        ],
        options_title="Repairs and reports",
        options=[
            ("Leak repair", "Find the source, fix it, and check it during the next rain.", ["Most done in one visit", "Priced on site"]),
            ("Flashing &amp; chimneys", "Re-flash chimneys, walls and skylights, and re-seal crowns.", ["Common leak source", "Priced on site"]),
            ("Real-estate inspections", "A roof report for buyers, sellers and PCS moves, with remaining life estimated.", ["Written report", "Free demo"]),
            ("Maintenance tune-up", "Seal exposed nails, replace boots, clear valleys and gutters every few years.", ["Extends roof life", "Priced per roof"]),
        ],
        steps=[
            ("Call or text", "Tell us where the water shows up and when it started."),
            ("Inspection", "Attic first, then the roof. We photograph the source."),
            ("Quote", "A fixed price for the repair before we start."),
            ("Repair", "Most repairs are done the same visit."),
            ("Follow-up", "We check in after the next real rain to make sure it's dry."),
        ],
        signs_title="Don't wait on these",
        signs=[
            ("A ceiling stain that grows", "after each rain."),
            ("Drips around a chimney or skylight.", "Flashing is the usual culprit."),
            ("Musty smell or damp insulation", "in the attic."),
            ("Peeling paint or soft wood", "on fascia and soffits."),
        ],
        faqs=[
            ("Is the inspection really free?", "Yes. Inspections are free inside our service area. You get the photos and our recommendation either way."),
            ("Repair or replace?", "If the roof is otherwise sound, repair it. We only recommend a replacement when the shingles themselves are worn out or damage is widespread."),
            ("Can you match my shingles?", "We match color and style as closely as possible. Discontinued and weathered shingles never match perfectly, and we'll tell you up front."),
            ("Do you do roof reports for a home sale or PCS move?", "Yes. We write a report with photos and estimated remaining life that you can share with agents and buyers."),
        ],
    ),
    dict(
        slug="gutters", name="Gutters", nav="Seamless aluminum, guards, downspouts",
        img="gutters", alt="Aluminum gutter and downspout along the edge of a roof", tag="Seamless",
        card="5\" and 6\" seamless aluminum formed on site, with downspouts and leaf guards in colors to match your trim.",
        chips=["Seamless aluminum", "Leaf guards", "Downspouts"],
        h1='Seamless <span>gutters</span>', need="Gutters",
        title="Seamless Gutters in Fayetteville, NC",
        desc="Seamless aluminum gutters, downspouts and leaf guards formed on site in Fayetteville, NC and 50 miles around. Colors to match your trim.",
        sub="Seamless aluminum formed on site, sized for Carolina downpours, with guards that handle pine needles.",
        intro=[
            "Gutters are part of the roof system. When they overflow or pull away, water ends up behind the fascia, in the crawlspace and against the foundation. We form seamless aluminum on site to the exact length of each run, so there are no joints to leak except at the corners.",
            "Sandhills lots are full of longleaf pines, so we size downspouts and pick guards with pine needles in mind.",
        ],
        included=[
            ("Seamless runs.", "Formed on site from coil to the exact length of each wall."),
            ("Hidden hangers.", "Screwed into the fascia every two feet, not spiked."),
            ("Right-size downspouts.", "Enough of them, in the right spots, with extensions away from the foundation."),
            ("Drip edge check.", "So water lands in the gutter, not behind it."),
            ("Haul-away.", "Old gutters removed and recycled."),
        ],
        options_title="Options",
        options=[
            ('5" K-style', "The standard for most homes. Plenty for average roofs and lots without heavy tree cover.", ["Most homes", "Dozens of colors"]),
            ('6" K-style', "Carries about 40% more water. Best for big or steep roofs and long runs.", ["Steep &amp; large roofs", "3×4 downspouts"]),
            ("Leaf &amp; needle guards", "Fine-mesh guards that keep out pine needles as well as leaves.", ["Less cleaning", "Fits new or existing"]),
            ("Downspouts &amp; drainage", "Extensions, splash blocks and tie-ins to underground drains.", ["Protects foundation", "Priced per run"]),
        ],
        steps=[
            ("Measure", "Every run, corner and downspout location."),
            ("Pick a color", "Matched to your trim, or a contrast if you prefer."),
            ("Form on site", "Gutters are rolled from coil in our truck."),
            ("Hang &amp; seal", "Hidden hangers, sealed corners and outlets."),
            ("Water test", "We run a hose to check the flow before we leave."),
        ],
        signs_title="Time for new gutters if",
        signs=[
            ("Water spills over the front", "in a hard rain."),
            ("Gutters sag or pull away", "from the fascia."),
            ("Seams drip", "or you see rust and peeling paint at the joints."),
            ("Puddles or erosion", "along the foundation."),
        ],
        faqs=[
            ("5-inch or 6-inch?", "Most homes are fine with 5-inch. We recommend 6-inch for large or steep roofs, long runs, and valleys that dump a lot of water in one spot."),
            ("Do guards work with pine needles?", "Fine stainless mesh guards do. Basic screens and foam inserts tend to trap needles, so we don't recommend them under pines."),
            ("Should I replace gutters with my roof?", "If they're more than 15 years old or the roof is getting new drip edge, it's the cheapest time to do it. We can quote both together."),
            ("Do you clean gutters?", "We clean them as part of inspections and maintenance plans, and we can add guards so you don't have to."),
        ],
    ),
    dict(
        slug="siding", name="Siding", nav="Vinyl, fiber cement, soffit and fascia",
        img="siding", alt="A two-story building clad in white vinyl lap siding under storm clouds", tag="Storm repair",
        card="Vinyl, fiber cement and engineered wood siding, plus soffit, fascia and trim. Full replacements and storm repairs matched to the existing walls.",
        chips=["Vinyl", "Fiber cement", "Soffit &amp; fascia"],
        h1='Siding <span>installation &amp; repair</span>', need="Siding",
        title="Siding Installation & Repair in Fayetteville, NC",
        desc="Vinyl and fiber cement siding installation, replacement and storm repair in Fayetteville, NC. House wrap, trim and soffit included. Free inspections.",
        sub="Vinyl, fiber cement and engineered wood siding, plus soffit, fascia and trim. Full replacements, storm repairs and color matching for one damaged wall.",
        intro=[
            "Siding is the other half of your home's weather shell. When it cracks, warps or comes loose, rain gets behind it and soaks the sheathing and framing, and in our humidity that turns into rot and mold faster than most people expect. Hail and wind that damage a roof usually damage the siding on the same side of the house, too.",
            "Every replacement goes down to the sheathing, so we can fix soft spots and put on new house wrap and flashing before the new siding goes up. Hail that cracks vinyl usually means the roof took hits too, so we inspect both and document everything for a single insurance claim.",
        ],
        included=[
            ("Full removal and sheathing check.", "Rotten boards replaced at a price we quote up front."),
            ("New house wrap.", "Lapped and taped so water that gets behind the siding drains out instead of in."),
            ("Flashing at every opening.", "Including kick-out flashing where a roof meets a wall, where most hidden rot starts."),
            ("New trim, corners and J-channel", "in a matching or contrasting color."),
            ("Soffit and fascia", "wrapped or replaced so the eaves match the new walls and stay vented."),
            ("Haul-off and cleanup", "with a magnetic sweep around the whole house."),
        ],
        options_title="Siding options",
        options=[
            ("Standard vinyl", "Low cost and low upkeep. Never needs paint. Can crack in hail or warp near a reflective window.", ["20–30 yr", "$450–$750 / sq demo"]),
            ("Insulated vinyl", "Foam-backed panels that stand straighter, resist dents better and add some insulation.", ["30–40 yr", "$700–$1,100 / sq demo"]),
            ("Fiber cement", "Resists fire, rot, termites and hail. Factory-painted finishes hold color 15+ years.", ["30–50 yr", "$900–$1,400 / sq demo"]),
            ("Engineered wood", "Real wood look, lighter than fiber cement, treated against rot and termites.", ["25–30 yr", "$750–$1,150 / sq demo"]),
            ("Board &amp; batten", "Vertical profile in vinyl or fiber cement, popular on farmhouse styles and accent gables.", ["25–50 yr", "$700–$1,300 / sq demo"]),
            ("Soffit &amp; fascia wrap", "Vented vinyl or aluminum soffit and aluminum-wrapped fascia. No more painting eaves.", ["25–40 yr", "$12–$24 / ft demo"]),
        ],
        steps=[
            ("Free inspection", "We check every wall, press-test the areas that rot first, and photograph any storm damage."),
            ("Material &amp; color", "Full-size samples so you see colors and profiles against your roof, brick and trim in daylight."),
            ("Written quote", "Price per square, trim, soffit and fascia, and sheathing repair listed separately."),
            ("Strip, repair, wrap", "One or two walls at a time, so the house is never left open overnight."),
            ("Install &amp; walkthrough", "Siding, trim and soffit go up, then a final walkthrough and a magnetic sweep."),
        ],
        signs_title="Signs your siding needs attention",
        signs=[
            ("Cracked, holed or missing panels,", "often on the side that faced the last hailstorm."),
            ("Warped or buckled panels.", "Vinyl nailed too tight can't expand in summer heat."),
            ("Soft spots when you press on the wall,", "especially below windows and at roof lines."),
            ("Peeling paint or swelling", "on wood or hardboard siding."),
        ],
        faqs=[
            ("Can you replace just the damaged panels?", "Usually. For storm damage on one or two walls, we match the profile and color. If the original has faded or been discontinued, we show you the closest match before any work starts."),
            ("Vinyl or fiber cement?", "Vinyl costs less and never needs paint. Fiber cement costs more but stands up to hail, fire and termites and looks closer to painted wood."),
            ("Does insurance cover hail-damaged siding?", "Often, when the damage is from a covered storm. We photograph every crack and dent, write a line-item scope and meet the adjuster at the house."),
            ("How long does a siding job take?", "About three to seven days for a typical one- or two-story home, depending on size, trim and sheathing repair."),
        ],
    ),
]
SVC = {s["slug"]: s for s in SERVICES}

# --------------------------------------------------------------------------- towns
COUNTIES = [
    ("Cumberland", "Cumberland County"),
    ("Harnett", "Harnett County"),
    ("Robeson", "Robeson County"),
    ("Sampson", "Sampson County"),
    ("Moore", "Moore County"),
    ("Hoke & Scotland", "Hoke & Scotland counties"),
    ("Lee & Johnston", "Lee & Johnston counties"),
    ("Bladen", "Bladen County"),
]
# (name, lat, lon, county, county group, local note)
TOWNS = [
    ("Fayetteville", 35.0527, -78.8784, "Cumberland", "Cumberland", "Our home base. Fayetteville roofs run from the older homes in Haymount and the brick ranches off Raeford Road to newer subdivisions toward Gray's Creek and Jack Britt. Most city calls get an inspection the same or next day."),
    ("Hope Mills", 34.9704, -78.9453, "Cumberland", "Cumberland", "Hope Mills sits just south of Fayetteville around Hope Mills Lake, with a mix of 1970s and '80s brick ranches and newer subdivisions off Rockfish and Camden roads. Plenty of those original roofs are on their second or third storm season past due."),
    ("Spring Lake", 35.1679, -78.9728, "Cumberland", "Cumberland", "Spring Lake borders Fort Bragg, so a lot of our work here is for military families and landlords renting to them. We schedule around PCS dates and can send photo reports to owners who are stationed elsewhere."),
    ("Fort Bragg", 35.139, -79.006, "Cumberland", "Cumberland", "On-post family housing is maintained by the post's privatized housing partner, so we don't work on those homes. We do serve the off-post neighborhoods around every gate, in Spring Lake, west Fayetteville, Raeford and Hoke County, where most Bragg families buy."),
    ("Eastover", 35.0938, -78.7814, "Cumberland", "Cumberland", "Eastover is a small town across the Cape Fear River from Fayetteville, incorporated in 2007, with larger lots and many homes built in the 1990s and 2000s. Those roofs are reaching replacement age now."),
    ("Stedman", 35.0129, -78.6936, "Cumberland", "Cumberland", "Stedman is a rural town in eastern Cumberland County along NC-24. Alongside houses, we put a lot of metal on barns, shops and equipment sheds out here."),
    ("Wade", 35.1610, -78.7350, "Cumberland", "Cumberland", "Wade sits along I-95 in northern Cumberland County. Homes here sit on open, rural lots, which means more wind exposure and more lifted shingles after a storm."),
    ("Godwin", 35.2157, -78.6806, "Cumberland", "Cumberland", "Godwin is one of the smallest towns in Cumberland County, up near the Harnett line. We handle farmhouses, outbuildings and metal retrofits here as often as shingle roofs."),
    ("Linden", 35.2546, -78.7486, "Cumberland", "Cumberland", "Linden is a small town in northern Cumberland County near the Harnett line, with rural homes on wooded lots where falling limbs are a regular storm call."),
    ("Lillington", 35.3993, -78.8158, "Harnett", "Harnett", "Lillington is Harnett County's seat, on the Cape Fear River near Campbell University. New subdivisions along US-421 and NC-210 sit next to older homes downtown, and we work on both."),
    ("Dunn", 35.3063, -78.6089, "Harnett", "Harnett", "Dunn is an I-95 town with a historic downtown and the General William C. Lee Airborne Museum. Older homes here often have two layers of shingles, so a full tear-off is usually the first step."),
    ("Erwin", 35.3268, -78.6761, "Harnett", "Harnett", "Erwin grew up around the old Erwin Mills denim plant. Mill houses and post-war homes are common, and many need decking repairs when the old roof comes off."),
    ("Angier", 35.5071, -78.7392, "Harnett", "Harnett", "Angier, home of the Crape Myrtle Festival, is growing fast as Raleigh commuters move south. That means a lot of builder-grade roofs from the 2000s that are now due for replacement."),
    ("Lumberton", 34.6182, -79.0086, "Robeson", "Robeson", "Lumberton is Robeson County's seat on the Lumber River. Hurricane Matthew in 2016 and Florence in 2018 both hit the city hard, and many roofs patched after those storms are now ready for a proper replacement."),
    ("St. Pauls", 34.8065, -78.9711, "Robeson", "Robeson", "St. Pauls is a small town along I-95 in northern Robeson County, a short drive down from Hope Mills. We see a mix of older frame homes and brick ranches here."),
    ("Parkton", 34.9024, -79.0117, "Robeson", "Robeson", "Parkton is a small town in northern Robeson County, just below the Cumberland line. Rural lots and tall trees make storm checks a regular call here."),
    ("Red Springs", 34.8152, -79.1831, "Robeson", "Robeson", "Red Springs is home to the historic Flora Macdonald College campus and plenty of older homes, where we often replace flashing and chimney details along with the shingles."),
    ("Pembroke", 34.6810, -79.1950, "Robeson", "Robeson", "Pembroke is home to UNC Pembroke and the Lumbee Tribe. We work on family homes, rentals near campus and church and commercial buildings in town."),
    ("Clinton", 34.9979, -78.3233, "Sampson", "Sampson", "Clinton is Sampson County's seat, with a historic downtown and older homes in town and farm and ag buildings across the county. We do as much metal and commercial work here as shingles."),
    ("Roseboro", 34.9535, -78.5106, "Sampson", "Sampson", "Roseboro is a small town in western Sampson County. Open farmland means strong wind exposure, and wind-lifted shingles are the most common call we get here."),
    ("Autryville", 34.9985, -78.6406, "Sampson", "Sampson", "Autryville is a small town on the Cumberland–Sampson line, about twenty minutes from our shop. Homes, barns and shops here are a mix of shingle and metal."),
    ("Salemburg", 35.0157, -78.5003, "Sampson", "Sampson", "Salemburg is a small Sampson County town and home of the North Carolina Justice Academy. We handle homes in town and farm buildings on the surrounding land."),
    ("Southern Pines", 35.1740, -79.3923, "Moore", "Moore", "Southern Pines is horse and golf country under tall longleaf pines. Older homes near downtown and wooded lots everywhere mean limbs, needles in the gutters and lots of flashing work."),
    ("Aberdeen", 35.1315, -79.4295, "Moore", "Moore", "Aberdeen has a historic downtown, older homes, and fast-growing subdivisions along US-1 and US-15-501. We see original roofs from the early 2000s building boom coming due."),
    ("Pinehurst", 35.1954, -79.4695, "Moore", "Moore", "Pinehurst homes often sit in neighborhoods with HOA or architectural rules on roof color and material. We bring samples and help with the approval paperwork before we order."),
    ("Vass", 35.2546, -79.2814, "Moore", "Moore", "Vass is a small town in northern Moore County. Wooded lots and the pines that come with them make storm and limb damage a regular call."),
    ("Raeford", 34.9810, -79.2242, "Hoke", "Hoke & Scotland", "Raeford is Hoke County's seat and home of the North Carolina Turkey Festival. Much of Hoke's growth comes from Fort Bragg families, so newer subdivisions are a big part of our work here."),
    ("Laurinburg", 34.7740, -79.4628, "Scotland", "Hoke & Scotland", "Laurinburg is Scotland County's seat and home of St. Andrews University. We work on older homes in town, rentals and commercial roofs downtown."),
    ("Sanford", 35.4799, -79.1803, "Lee", "Lee & Johnston", "Sanford, Lee County's seat, calls itself the Brick Capital of the USA, and plenty of its homes are brick ranches with roofs from the '70s through the '90s."),
    ("Broadway", 35.4582, -79.0531, "Lee", "Lee & Johnston", "Broadway is a small town in eastern Lee County on the way to Lillington. Rural lots here mean we often do the house and the shop in one trip."),
    ("Benson", 35.3821, -78.5486, "Johnston", "Lee & Johnston", "Benson sits near where I-95 meets I-40 and is known for Benson Mule Days. We see older homes in town and new subdivisions going up around it."),
    ("Smithfield", 35.5085, -78.3394, "Johnston", "Lee & Johnston", "Smithfield is Johnston County's seat on the Neuse River and home of the Ava Gardner Museum. It's near the edge of our 50 miles, and inspections here are still free."),
    ("Elizabethtown", 34.6293, -78.6053, "Bladen", "Bladen", "Elizabethtown is Bladen County's seat on the Cape Fear River. It sits closer to the coast than Fayetteville, so hurricanes arrive here with more wind behind them."),
]
COUNTY_NOTES = {
    "Cumberland": "Cumberland County takes the brunt of tropical systems that track up I-95. Matthew in 2016 and Florence in 2018 both brought days of wind and flooding rain.",
    "Harnett": "Spring hail and summer thunderstorms hit Harnett most years, and the tropical storms that reach Fayetteville usually reach here a few hours later.",
    "Robeson": "Robeson County flooded in both Matthew and Florence. Driven rain gets under any lifted shingle, so we check every roof here for wind damage after a named storm.",
    "Sampson": "Sampson County's open farmland gives wind a long run at every roof. Ridge caps and the first rows of shingles at the eaves take the worst of it.",
    "Moore": "Moore County's tall pines drop limbs in every big blow, and pine needles pack valleys and gutters. Both cause leaks we fix every week.",
    "Hoke": "Hoke County catches the same tropical systems as Fayetteville, plus summer thunderstorms rolling in from the west.",
    "Scotland": "Scotland County sits on the South Carolina line, right in the path of tropical systems coming inland from the coast.",
    "Lee": "Lee County gets spring hail and severe summer storms more often than people expect. Hail checks after a storm are free.",
    "Johnston": "Johnston County sees strong summer storms and the tail end of hurricanes moving up I-95 and I-40.",
    "Bladen": "Bladen County is closer to the coast than Fayetteville, so hurricanes arrive with more wind behind them. Wind-rated installs matter here.",
}
REVIEWS = {
    "Hope Mills": ("Tasha R.", "Shingle replacement", "Hail hit our neighborhood in April. They met the adjuster, got the whole roof approved, and had new shingles on in a day."),
    "Spring Lake": ("Marcus J.", "Full replacement", "We PCS'd in six weeks and needed the roof done before listing. The military discount helped and the crew left the yard spotless."),
    "Lumberton": ("Keisha P.", "Storm repair", "A limb came through our roof during a tropical storm. They had a tarp on it that evening and handled the claim from there."),
}
HERO_ROT = ["crew-work", "hero-crew", "bundles-on-roof", "shingles-new", "tarp-crew", "metal-seam"]


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def miles(a, b):
    return math.hypot((a[0] - b[0]) * 69, (a[1] - b[1]) * 69.17 * math.cos(math.radians(HQ[0])))


def direction(lat, lon):
    dy, dx = lat - HQ[0], (lon - HQ[1]) * math.cos(math.radians(HQ[0]))
    ang = (math.degrees(math.atan2(dx, dy)) + 360) % 360
    return ["north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"][round(ang / 45) % 8]


T = []
for i, (name, la, lo, county, group, note) in enumerate(TOWNS):
    d = miles((la, lo), HQ)
    T.append(dict(name=name, slug=slugify(name), lat=la, lon=lo, county=county, group=group, note=note,
                  mi=round(d), where="Home base" if d < 1 else f"{round(d)} miles {direction(la, lo)} of Fayetteville",
                  img=HERO_ROT[i % len(HERO_ROT)]))
TOWN = {t["name"]: t for t in T}


def towns_in(group):
    return [t for t in T if t["group"] == group]


# --------------------------------------------------------------------------- shared chrome
ICON_PHONE = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M6.6 10.8a15.1 15.1 0 0 0 6.6 6.6l2.2-2.2a1 1 0 0 1 1-.25 11.4 11.4 0 0 0 3.6.57 1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 17 0 0 1 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.25.2 2.45.57 3.57a1 1 0 0 1-.25 1z"/></svg>'
ICON_ARROW = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>'
LOGO = '<svg viewBox="0 0 48 48" aria-hidden="true"><rect width="48" height="48" rx="6" fill="#1D1160"/><path d="M7 28 24 13l17 15" fill="none" stroke="#fff" stroke-width="4.2" stroke-linecap="square"/><path d="M14 32 24 23.5 34 32" fill="none" stroke="#00A3B5" stroke-width="3.6" stroke-linecap="square"/><path d="M20 38h8" stroke="#A1A1A4" stroke-width="3.2"/></svg>'
LOGO_FOOT = '<svg viewBox="0 0 48 48" aria-hidden="true"><rect width="48" height="48" rx="6" fill="#00788C"/><path d="M7 28 24 13l17 15" fill="none" stroke="#fff" stroke-width="4.2" stroke-linecap="square"/><path d="M14 32 24 23.5 34 32" fill="none" stroke="#1D1160" stroke-width="3.6" stroke-linecap="square"/></svg>'


def home(R):
    return R or "./"


def header(R):
    svc_dd = "".join(f'<a href="{R}services/{s["slug"]}/">{s["name"].replace("&", "&amp;")}<small>{s["nav"]}</small></a>' for s in SERVICES)
    area_dd = "".join(
        f'<div><h4>{label.replace("&", "&amp;")}</h4>' + "".join(f'<a href="{R}areas/{t["slug"]}/">{t["name"]}</a>' for t in towns_in(g)) + "</div>"
        for g, label in COUNTIES)
    m_svc = "".join(f'<a href="{R}services/{s["slug"]}/">{s["name"].replace("&", "&amp;")}</a>' for s in SERVICES)
    m_area = "".join(
        f'<h4>{label.replace("&", "&amp;")}</h4>' + "".join(f'<a href="{R}areas/{t["slug"]}/">{t["name"]}</a>' for t in towns_in(g))
        for g, label in COUNTIES)
    return f'''<header class="site">
  <div class="wrap">
    <a class="brand" href="{home(R)}" aria-label="Faircloth Roofing home">
      {LOGO}
      <span><b>Faircloth Roofing</b><small>Fayetteville · NC</small></span>
    </a>
    <nav class="main" aria-label="Main">
      <div class="dd"><a href="{R}services/">Services</a><div class="dd-panel"><div class="svc-dd">{svc_dd}<a class="all" href="{R}services/">All services</a></div></div></div>
      <div class="dd"><a href="{R}areas/">Areas</a><div class="dd-panel dd-areas"><div>{area_dd}<a class="all" href="{R}areas/">All 33 towns we serve</a></div></div></div>
      <a href="{R}#storm">Storm claims</a><a href="{R}#estimate">Estimate</a><a href="{R}#reviews">Reviews</a><a href="{R}#faq">FAQ</a>
    </nav>
    <a class="btn btn-teal hdr-call" href="{TEL}" aria-label="Call {PHONE}, demo number">
      {ICON_PHONE}
      {PHONE}</a>
    <button class="icon-btn" id="themeBtn" type="button" aria-label="Color theme: system">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 0 0 18z" fill="currentColor"/></svg>
    </button>
    <details class="menu">
      <summary class="icon-btn" aria-label="Open menu"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg></summary>
      <div class="panel">
        <a href="{home(R)}">Home</a>
        <details class="grp"><summary>Services</summary><div><a href="{R}services/">All services</a>{m_svc}</div></details>
        <details class="grp"><summary>Areas served</summary><div><a href="{R}areas/">All areas</a>{m_area}</div></details>
        <a href="{R}#storm">Storm &amp; insurance</a><a href="{R}#estimate">Instant estimate</a><a href="{R}#warranty">Warranties</a><a href="{R}#reviews">Reviews</a><a href="{R}#faq">FAQ</a><a href="{R}#contact">Free inspection</a>
      </div>
    </details>
  </div>
</header>'''


def footer(R):
    svc = "".join(f'<li><a href="{R}services/{s["slug"]}/">{s["name"].replace("&", "&amp;")}</a></li>' for s in SERVICES)
    top = ["Fayetteville", "Hope Mills", "Spring Lake", "Raeford", "Lumberton", "Southern Pines", "Lillington", "Sanford"]
    areas = "".join(f'<li><a href="{R}areas/{TOWN[n]["slug"]}/">{n}</a></li>' for n in top)
    return f'''<footer class="site">
  <div class="wrap">
    <div>
      <a class="brand" href="{home(R)}">{LOGO_FOOT}<span><b>Faircloth Roofing</b><small>Fayetteville · NC</small></span></a>
      <p style="margin-top:14px;max-width:40ch">Residential and commercial roofing for Fayetteville, Fort Bragg and the Sandhills.</p>
      <ul style="margin-top:16px"><li><a href="{TEL}">{PHONE}</a> <span class="demo">demo</span></li><li>hello@fairclothroofing.example</li></ul>
    </div>
    <div><h4>Services</h4><ul>{svc}<li><a href="{R}services/">All services</a></li></ul></div>
    <div><h4>Areas served</h4><ul>{areas}<li><a href="{R}areas/">All 33 towns</a></li></ul></div>
    <div><h4>Explore</h4><ul><li><a href="{R}#storm">Storm &amp; insurance</a></li><li><a href="{R}#estimate">Instant estimate</a></li><li><a href="{R}#warranty">Warranties</a></li><li><a href="{R}#reviews">Reviews</a></li><li><a href="{R}#faq">FAQ</a></li><li><a href="{R}#contact">Free inspection</a></li></ul></div>
    <!--credits-->
    <p class="legal">© <span id="yr">2026</span> Faircloth Roofing. Demo website: phone, email, reviews, ratings, certifications, discounts, prices and company figures are placeholders. Photos are stock images from Wikimedia Commons, not Faircloth jobs.</p>
  </div>
</footer>'''


STRIP = '''<div class="strip">
  <div class="wrap">
    <span><span class="demo">Demo site</span> <span class="hide-sm">Phone, reviews and figures marked DEMO are placeholders.</span></span>
    <span>Mon–Sat · <b>24/7 storm emergencies</b> <span class="demo">demo</span></span>
  </div>
</div>'''


def callbar(R, q=""):
    return f'''<nav class="callbar" aria-label="Quick contact">
  <a href="{TEL}">{ICON_PHONE}Call now</a>
  <a class="go" href="{R}{q}#contact">Free inspection</a>
</nav>'''


def contact_q(town=None, need=None):
    parts = []
    if town:
        parts.append("town=" + town.replace(" ", "+"))
    if need:
        parts.append("need=" + need.replace(" ", "+").replace("/", "%2F"))
    return ("?" + "&amp;".join(parts)) if parts else ""


def page(path, title, desc, R, body, crumbs, q=""):
    ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": BASE_URL + p} for i, (n, p) in enumerate(crumbs)]}
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{escape(title)} | Faircloth Roofing</title>
<meta name="description" content="{escape(desc)}">
<link rel="canonical" href="{BASE_URL}{path}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700;800&family=Barlow:wght@400;500;600;700&display=swap">
<link rel="stylesheet" href="{R}site.css">
<script type="application/ld+json">{json.dumps(ld)}</script>
</head>
<body>

{STRIP}

{header(R)}

<main id="top">
{body}
</main>

{footer(R)}

{callbar(R, q)}

<script src="{R}site.js"></script>
</body>
</html>
'''


def crumbs_html(crumbs, R):
    items = []
    for i, (n, p) in enumerate(crumbs):
        n = escape(n)
        if i == len(crumbs) - 1:
            items.append(f'<li aria-current="page">{n}</li>')
        else:
            items.append(f'<li><a href="{R}{p}">{n}</a></li>')
    return f'<nav class="crumbs" aria-label="Breadcrumb"><ol>{"".join(items)}</ol></nav>'


def img_tag(name, alt, R, extra=""):
    w, h = IMG[name]
    return f'<img src="{R}img/{name}.jpg" alt="{alt}" width="{w}" height="{h}"{extra}>'


def phero(R, crumbs, kicker, h1, sub, img, q, alt=""):
    return f'''<section class="phero" aria-labelledby="page-title">
  {img_tag(img, alt, R, ' fetchpriority="high"')}
  <div class="wrap">
    {crumbs_html(crumbs, R)}
    <div class="inner">
      <p class="kicker">{kicker}</p>
      <h1 id="page-title">{h1}</h1>
      <p class="sub">{sub}</p>
      <div class="ctas">
        <a class="btn btn-teal" href="{R}{q}#contact">Free roof inspection {ICON_ARROW}</a>
        <a class="btn btn-line" href="{TEL}">{ICON_PHONE}{PHONE}</a>
      </div>
    </div>
  </div>
</section>'''


def cta_band(R, q, title="Book your free roof inspection", text="Tell us what's going on and we'll call to set a time, usually within one business day."):
    return f'''<section class="cta-band" aria-label="Free inspection">
  <div class="wrap">
    <div>
      <p class="kicker">Free inspection</p>
      <h2>{title}</h2>
      <p>{text} <span class="demo">demo</span></p>
    </div>
    <div class="ctas">
      <a class="btn btn-teal" href="{R}{q}#contact">Request inspection {ICON_ARROW}</a>
      <a class="btn btn-line" href="{TEL}">{ICON_PHONE}Call {PHONE}</a>
    </div>
  </div>
</section>'''


def svc_cards(R, heading="h3"):
    out = []
    for s in SERVICES:
        url = f'{R}services/{s["slug"]}/'
        chips = "".join(f"<li>{c}</li>" for c in s["chips"])
        out.append(f'''      <article class="svc">
        <figure>{img_tag(s["img"], s["alt"], R, ' loading="lazy"')}<span class="tag">{s["tag"]}</span></figure>
        <div class="body"><{heading}><a href="{url}">{s["name"].replace("&", "&amp;")}</a></{heading}><p>{s["card"]}</p>
          <ul>{chips}</ul>
          <a class="more" href="{url}" aria-label="More about {s["name"].replace("&", "&amp;").lower()}">Learn more {ICON_ARROW}</a></div>
      </article>''')
    return '    <div class="svc-grid">\n' + "\n".join(out) + "\n    </div>"


LAZY = ' loading="lazy"'


def mini_services(R, town=None, exclude=None):
    out = []
    for s in SERVICES:
        if s["slug"] == exclude:
            continue
        label = s["name"].replace("&", "&amp;")
        out.append(f'<a class="mini" href="{R}services/{s["slug"]}/">{img_tag(s["img"], "", R, LAZY)}<span><b>{label}</b><small>{s["nav"]}</small></span></a>')
    return '<div class="mini-grid">' + "".join(out) + "</div>"


def county_grid(R):
    boxes = []
    for g, label in COUNTIES:
        lis = "".join(
            f'<li><a href="{R}areas/{t["slug"]}/">{t["name"]}</a><span>{"Home base" if t["mi"] < 1 else str(t["mi"]) + " mi"}</span></li>'
            for t in towns_in(g))
        boxes.append(f'<div class="county"><h3>{label.replace("&", "&amp;")}</h3><ul>{lis}</ul></div>')
    return '<div class="area-grid" id="counties">' + "".join(boxes) + "</div>"


def checks(items):
    return '<ul class="checks">' + "".join(f"<li><span><b>{a}</b> {b}</span></li>" for a, b in items) + "</ul>"


def faq_block(faqs, title="Common questions"):
    qs = "".join(f'<details class="q"><summary>{q}</summary><p>{a}</p></details>' for q, a in faqs)
    return f'''<section id="faq-page" aria-labelledby="faq-title">
  <div class="wrap faq-grid">
    <div class="sec-head"><p class="kicker">FAQ</p><h2 id="faq-title">{title}</h2><p class="lede">Don't see yours? Call and a real roofer will answer.</p></div>
    <div>{qs}</div>
  </div>
</section>'''


# --------------------------------------------------------------------------- service pages
def service_page(s):
    R = "../../"
    q = contact_q(need=s["need"])
    crumbs = [("Home", ""), ("Services", "services/"), (s["name"], f'services/{s["slug"]}/')]
    opts = "".join(
        f'<div class="opt"><h3>{n}</h3><p>{d}</p><div class="meta">' + "".join(
            f'<span>{m.replace(" demo", "")}{" <span class=demo>demo</span>" if m.endswith(" demo") else ""}</span>' for m in meta) + "</div></div>"
        for n, d, meta in s["options"])
    steps = "".join(f"<li><div><h3>{h}</h3><p>{p}</p></div></li>" for h, p in s["steps"])
    intro = "".join(f"<p>{p}</p>" for p in s["intro"])
    chip_groups = "".join(
        f'<div><h3>{label.replace("&", "&amp;")}</h3><ul class="chips">' + "".join(
            f'<li><a href="{R}areas/{t["slug"]}/">{t["name"]}</a></li>' for t in towns_in(g)) + "</ul></div>"
        for g, label in COUNTIES)
    est = "" if s["slug"] in ("siding", "gutters", "roof-repair", "storm-damage-repair") else \
        f'<a class="btn btn-purple" href="{R}#estimate">Price it in 20 seconds</a>'
    body = f'''{phero(R, crumbs, "Faircloth Roofing services", s["h1"], s["sub"], s["img"], q, s["alt"])}

<section aria-labelledby="ov-title">
  <div class="wrap two">
    <div class="prose">
      <p class="kicker">Overview</p>
      <h2 id="ov-title">What you get</h2>
      {intro}
      {checks(s["included"])}
    </div>
    <aside class="facts" aria-label="At a glance">
      <h3>At a glance</h3>
      <dl>
        <dt>Service area</dt><dd>Fayetteville + 50 mi</dd>
        <dt>Inspection</dt><dd>Free</dd>
        <dt>Workmanship warranty</dt><dd>25 yr <span class="demo">demo</span></dd>
        <dt>Military discount</dt><dd>12% <span class="demo">demo</span></dd>
      </dl>
      <a class="btn btn-teal" href="{R}{q}#contact">Book a free inspection</a>
      {est}
    </aside>
  </div>
</section>

<section class="alt" aria-labelledby="opt-title">
  <div class="wrap">
    <div class="sec-head"><p class="kicker">Options</p><h2 id="opt-title">{s["options_title"]}</h2>
      <p class="lede">Prices are demo ranges per installed square (100 sq ft). Your inspection turns them into a firm quote.</p></div>
    <div class="opt-grid{' c3' if len(s['options']) % 3 == 0 else ''}">{opts}</div>
  </div>
</section>

<section aria-labelledby="proc-title">
  <div class="wrap storm-grid">
    <div>
      <div class="sec-head" style="margin-bottom:24px"><p class="kicker">How it works</p><h2 id="proc-title">Start to finish</h2></div>
      <h3 style="font-size:1.3rem;text-transform:uppercase;letter-spacing:.05em">{s["signs_title"]}</h3>
      {checks(s["signs"])}
    </div>
    <ol class="steps">{steps}</ol>
  </div>
</section>

{faq_block(s["faqs"])}

<section class="alt" aria-labelledby="where-title">
  <div class="wrap">
    <div class="sec-head"><p class="kicker">Where we work</p><h2 id="where-title">{s["name"].replace("&", "&amp;")} near you</h2>
      <p class="lede">Free inspections in Fayetteville and every town within 50 miles.</p></div>
    <div class="chip-groups">{chip_groups}</div>
  </div>
</section>

<section aria-labelledby="rel-title">
  <div class="wrap">
    <div class="sec-head"><p class="kicker">More services</p><h2 id="rel-title">One crew for the whole house</h2></div>
    {mini_services(R, exclude=s["slug"])}
  </div>
</section>

{cta_band(R, q)}'''
    return page(f'services/{s["slug"]}/', s["title"], s["desc"], R, body, crumbs, q)


def services_hub():
    R = "../"
    crumbs = [("Home", ""), ("Services", "services/")]
    body = f'''{phero(R, crumbs, "What we do", 'Roofing <span>services</span>', "Replacements, storm repair, metal, commercial, leak repair, gutters and siding for homes and businesses across Fayetteville and the Sandhills.", "crew-work", "", "A roofing crew re-roofing a brick ranch house")}

<section aria-labelledby="svc-title">
  <div class="wrap">
    <div class="sec-head"><p class="kicker">Six services, one crew</p><h2 id="svc-title">Pick a service</h2>
      <p class="lede">Every job starts with a free inspection and a written scope, whatever the size.</p></div>
{svc_cards(R, "h2")}
  </div>
</section>

<section class="alt" aria-labelledby="unsure-title">
  <div class="wrap two">
    <div class="prose">
      <p class="kicker">Not sure what you need?</p>
      <h2 id="unsure-title">Start with a free inspection</h2>
      <p>A stain on the ceiling could be a $300 pipe boot or a roof at the end of its life. We get on the roof and in the attic, photograph what we find, and tell you which it is. If a repair will do, that's what we recommend.</p>
    </div>
    <aside class="facts"><h3>Serving 33 towns</h3><p>Fayetteville plus every town within 50 miles, from Sanford to Lumberton.</p><a class="btn btn-purple" href="{R}areas/">See areas served</a></aside>
  </div>
</section>

{cta_band(R, "")}'''
    return page("services/", "Roofing Services in Fayetteville, NC",
                "Roof replacement, storm and hail repair, metal, commercial flat roofs, leak repair, gutters and siding in Fayetteville, NC and 50 miles around.",
                R, body, crumbs)


# --------------------------------------------------------------------------- town pages
def town_page(t):
    R = "../../"
    name = t["name"]
    is_bragg = name == "Fort Bragg"
    q = contact_q(town=name)
    crumbs = [("Home", ""), ("Areas", "areas/"), (name, f'areas/{t["slug"]}/')]
    county_name = t["county"] + " County"
    h1 = 'Roofing near <span>Fort Bragg</span>' if is_bragg else f'{name} <span>roofing</span>'
    sub = ("Roof replacement, storm repair and inspections for military families in the neighborhoods around Fort Bragg. "
           "Active duty and veterans save 12%.") if is_bragg else \
        f"Roof replacement, storm repair, metal, commercial and gutters in {name}, NC. Free inspections and a crew that's {'right here' if t['mi'] < 1 else str(t['mi']) + ' miles away'}."
    near = sorted((x for x in T if x is not t), key=lambda x: miles((x["lat"], x["lon"]), (t["lat"], t["lon"])))[:6]
    near_html = "".join(
        f'<li><a href="{R}areas/{x["slug"]}/">{x["name"]}<small>{round(miles((x["lat"], x["lon"]), (t["lat"], t["lon"])))} mi</small></a></li>'
        for x in near)
    rev = ""
    if name in REVIEWS:
        who, job, quote = REVIEWS[name]
        rev = f'''<section class="alt" aria-labelledby="rev-title">
  <div class="wrap">
    <div class="sec-head"><p class="kicker">Reviews</p><h2 id="rev-title">From a {name} homeowner</h2></div>
    <article class="rev solo"><div class="stars" aria-label="5 out of 5 stars">★★★★★</div><blockquote>"{quote}"</blockquote><footer><b>{who}</b> <span class="demo">demo</span><br>{name} · {job}</footer></article>
  </div>
</section>'''
    distance = "Home base" if t["mi"] < 1 else f'{t["mi"]} mi {direction(t["lat"], t["lon"])}'
    faqs = [
        (f"Do you charge a trip fee to {name}?",
         "No. Our shop is in Fayetteville, so there's no travel to charge for and inspections are free." if t["mi"] < 1 else
         f"No. {name} is about {t['mi']} miles from our Fayetteville shop, inside our 50-mile service area, so inspections are free."),
        (f"How fast can you get to {name} after a storm?",
         "Active leaks come first. When water is getting in, we aim to have a tarp on the same day, and full inspections follow within a few days of a big storm. <span class=\"demo\">demo</span>"),
        ("Do you pull permits?",
         f"Yes. We pull the permit with whichever office handles your address, the town or {county_name}, and schedule the inspection."),
        ("Do you offer a military discount?",
         "Yes. Active duty, veterans, Guard and Reserve, military spouses and Gold Star families save 12% on a full replacement. <span class=\"demo\">demo</span>"),
    ]
    body = f'''{phero(R, crumbs, f"Areas served · {escape(county_name)}", h1, sub, t["img"], q)}

<section aria-labelledby="ov-title">
  <div class="wrap two">
    <div class="prose">
      <p class="kicker">Local roofers</p>
      <h2 id="ov-title">{"Serving Bragg families" if is_bragg else "Roofing in " + name}</h2>
      <p>{t["note"]}</p>
      <p>{COUNTY_NOTES[t["county"]]}</p>
      <p>Whatever brought you here, a leak, a storm, or a roof that's just old, the first step is the same: a free inspection with photos and a straight answer on repair versus replacement.</p>
    </div>
    <aside class="facts" aria-label="{name} at a glance">
      <h3>{name} at a glance</h3>
      <dl>
        <dt>County</dt><dd>{county_name}</dd>
        <dt>From our shop</dt><dd>{distance}</dd>
        <dt>Inspection</dt><dd>Free</dd>
        <dt>Storm tarping</dt><dd>24/7 <span class="demo">demo</span></dd>
      </dl>
      <a class="btn btn-teal" href="{R}{q}#contact">Book in {name}</a>
    </aside>
  </div>
</section>

<section class="alt" aria-labelledby="svc-title">
  <div class="wrap">
    <div class="sec-head"><p class="kicker">Services</p><h2 id="svc-title">What we do in {name}</h2>
      <p class="lede">The same crews, materials and warranties as in Fayetteville.</p></div>
    {mini_services(R)}
  </div>
</section>

{rev}

<section aria-labelledby="near-title">
  <div class="wrap">
    <div class="sec-head"><p class="kicker">Nearby</p><h2 id="near-title">Also serving near {name}</h2></div>
    <ul class="chips">{near_html}</ul>
    <p style="margin-top:22px"><a href="{R}areas/">See all 33 towns we serve</a></p>
  </div>
</section>

{faq_block(faqs, f"Roofing in {name}: questions")}

{cta_band(R, q, f"Free roof inspection in {name}")}'''
    title = "Roofing Near Fort Bragg, NC" if is_bragg else f"Roofing Contractor in {name}, NC"
    desc = (f"Roof replacement, storm and hail repair, metal roofs and gutters in {name}, NC ({county_name}). "
            f"Free inspections from Faircloth Roofing, {'based in Fayetteville' if t['mi'] < 1 else str(t['mi']) + ' miles away in Fayetteville'}.")
    return page(f'areas/{t["slug"]}/', title, desc, R, body, crumbs, q)


def areas_hub():
    R = "../"
    crumbs = [("Home", ""), ("Areas", "areas/")]
    body = f'''{phero(R, crumbs, "Service area", 'Fayetteville <span>plus 50 miles</span>', "33 towns across eight counties, from Sanford to Lumberton and Southern Pines to Clinton. Free inspections everywhere on this page.", "hero-crew", "", "A roofing crew tearing off old shingles")}

<section aria-labelledby="area-title">
  <div class="wrap">
    <div class="sec-head"><p class="kicker">Pick your town</p><h2 id="area-title">Towns we serve</h2>
      <p class="lede">Distances are straight-line miles from our Fayetteville shop. Don't see your town? If it's within about 50 miles, we'll come.</p></div>
    {county_grid(R)}
  </div>
</section>

<section class="alt" aria-labelledby="svc-title">
  <div class="wrap">
    <div class="sec-head"><p class="kicker">Services</p><h2 id="svc-title">Everything we do, everywhere we go</h2></div>
    {mini_services(R)}
  </div>
</section>

{cta_band(R, "")}'''
    return page("areas/", "Areas Served: Fayetteville, NC + 50 Miles",
                "Faircloth Roofing serves Fayetteville, NC and 33 towns within 50 miles: Hope Mills, Spring Lake, Raeford, Lumberton, Southern Pines, Sanford, Clinton and more.",
                R, body, crumbs)


# --------------------------------------------------------------------------- index sync
def sync_index():
    p = SITE / "index.html"
    s = p.read_text()
    s = re.sub(r"<header class=\"site\">.*?</header>", lambda m: header(""), s, count=1, flags=re.S)
    credits = re.search(r"<details class=\"credits\">.*?</details>", s, flags=re.S)
    foot = footer("").replace("<!--credits-->", credits.group(0) if credits else "")
    s = re.sub(r"<footer class=\"site\">.*?</footer>", lambda m: foot, s, count=1, flags=re.S)
    s = re.sub(r"<nav class=\"callbar\".*?</nav>", lambda m: callbar(""), s, count=1, flags=re.S)
    s = re.sub(r"<!--svc:start-->.*?<!--svc:end-->", lambda m: "<!--svc:start-->\n" + svc_cards("") + "\n    <!--svc:end-->", s, count=1, flags=re.S)
    s = re.sub(r"<!--areas:start-->.*?<!--areas:end-->", lambda m: "<!--areas:start-->" + county_grid("") + "<!--areas:end-->", s, count=1, flags=re.S)
    opts = "".join(f"<option>{n}</option>" for n in sorted(TOWN)) + "<option>Somewhere else nearby</option>"
    s = re.sub(r"<select id=\"cTown\">.*?</select>", lambda m: f'<select id="cTown">{opts}</select>', s, count=1, flags=re.S)
    p.write_text(s)


# services/roofing/ was published briefly; send it to the replacement page.
REDIRECT = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Roof replacement | Faircloth Roofing</title>
<link rel="canonical" href="{url}">
<meta http-equiv="refresh" content="0; url={to}">
<meta name="robots" content="noindex">
</head>
<body><p>This page moved to <a href="{to}">Roof replacement</a>.</p></body>
</html>
"""


def main():
    (SITE / "site.css").write_text((SRC / "base.css").read_text() + (SRC / "pages.css").read_text())
    (SITE / "services").mkdir(exist_ok=True)
    (SITE / "services" / "index.html").write_text(services_hub())
    for s in SERVICES:
        d = SITE / "services" / s["slug"]
        d.mkdir(exist_ok=True)
        (d / "index.html").write_text(service_page(s))
    (SITE / "areas").mkdir(exist_ok=True)
    (SITE / "areas" / "index.html").write_text(areas_hub())
    for t in T:
        d = SITE / "areas" / t["slug"]
        d.mkdir(exist_ok=True)
        (d / "index.html").write_text(town_page(t))
    d = SITE / "services" / "roofing"
    d.mkdir(exist_ok=True)
    (d / "index.html").write_text(REDIRECT.format(to="../roof-replacement/", url=BASE_URL + "services/roof-replacement/"))
    urls = ["", "services/", "areas/"] + [f'services/{x["slug"]}/' for x in SERVICES] + [f'areas/{t["slug"]}/' for t in T]
    (SITE / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                      + "".join(f"  <url><loc>{BASE_URL}{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    sync_index()
    print(f"Built {len(SERVICES)} service pages and {len(T)} town pages.")


if __name__ == "__main__":
    main()
