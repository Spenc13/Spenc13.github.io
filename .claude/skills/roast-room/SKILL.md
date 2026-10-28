---
name: roast-room
description: Run a "Roast Room" council - six simulated business advisors (Hormozi, Buffett, Paul Graham, Gary Vaynerchuk, Codie Sanchez, Sara Blakely) score the founder's options, argue, vote, and reach a verdict, published as a Roast Room artifact page. Use when the user types /roast-room, asks to "roast" a business decision, or wants the advisor council on a question.
---

# Roast Room

A council of six simulated advisors pressure-tests one business decision for the founders
(Spencer and Monique, Something Borrowed, Something You Corp. - an event rental company in
Charlotte, NC: tableware, flatware, arches, delivery and setup). The output is an artifact
page built from `template.html` in this folder.

## Flow

The council runs in stages. Each stage ends with a published (or republished) page and one
question back to the founder.

1. **Brief.** Restate the question in one sentence. Lay out the options as A, B, C, D
   (merge or add options if the user's list is incomplete, e.g. "mix them" becomes its own
   option with a stated order). Collect the facts: stage, money in hand, constraints, and
   what success looks like. Mark every assumption as an assumption. Before inventing
   numbers, check the user's existing artifacts (`Artifact` list/read). The investor deck
   "Something Borrowed, Something You Corp. - Investor Presentation (Web)" and earlier Roast
   Rooms hold the real terms. Ask at most one clarifying question, and only if the answer
   would change the scores.
2. **Round 1: Opening positions.** Each advisor gives a card (fields below) and scores every
   option out of 10. Then build the weighted scoreboard and list the 2-3 real fights.
   Publish the page and end with the "Before Round 2" question.
3. **Round 2: Debate.** Use the founder's answer. Advisors answer each other on the open
   fights, and any of them may change their scores. Add a debate section to the page and
   update the scoreboard.
4. **Round 3: Vote and Verdict.** Final scores, the winning option, the conditions that would
   flip it, and a this-week action list. Mark every progress step done.

If the user asks for the whole thing at once, run all rounds in one pass.

## The advisors

| Key | Full name | Pillar | Color | Init | Default weight |
|---|---|---|---|---|---|
| Hormozi | Alex Hormozi | Offers, pricing and sales | #d94a6a | AH | 3 |
| Buffett | Warren Buffett | Money and capital | #4c6a92 | WB | 3 |
| Graham | Paul Graham | Product and startups | #e05a2c | PG | 2 |
| Gary V | Gary Vaynerchuk | Marketing and attention | #9b5de5 | GV | 2 |
| Codie | Codie Sanchez | Buying and owning small businesses | #c2427f | CS | 2 |
| Sara | Sara Blakely | Consumer product and brand from zero | #a8861a | SB | 2 |

Re-weight to fit the question. A funding or deal-structure question gives Buffett and Codie
triple weight. A sales or pricing question gives Hormozi triple weight. A marketing question
gives Gary V triple weight. Say in the scoreboard note who counts how much.

Each advisor argues from the ideas they are publicly known for (for example: Hormozi on
offers, client-financed acquisition and never discounting; Buffett on never risking ruin and
not issuing stock cheaply; Graham on doing things that don't scale and avoiding debt;
Gary V on documenting, not creating, and giving value before asking; Codie on buying
boring assets and seller financing; Sara on self-funding, keeping ownership and a hero
product). **Do not invent direct quotes.** Paraphrase, or quote only a line you are sure is
real and widely attributed. Advisors must disagree where their known views disagree. A
unanimous Round 1 is called out as a warning sign, not a win.

## Card fields (one per advisor)

- `STANCE` - e.g. "Strong yes", "Yes, with conditions", "No"
- `OPTION SCORES` - "A x/10 · B x/10 · C x/10 · D x/10", plus a `scores` array in the same order
- `PILLAR SCORE`, `CONFIDENCE` (x/5), `RUIN RISK` (none/low/high), `DOOR` (one-way/two-way)
- `THE CALL` - one or two sentences
- `WHY` - 2-4 numbered reasons, plus a `why` array. Show the math, and label assumed numbers as assumed.
- `THE RISK I SEE`, `WHAT WOULD CHANGE MY MIND`, `WHAT I'D DO THIS WEEK`, `QUESTION FOR THE FOUNDER`

## Building the page

1. Copy `template.html` to the scratchpad (one file per council, named for the question).
2. Fill the header (date, question, one-line situation), the `progress` steps, the facts
   list, the `CARDS`, `META`, `OPTIONS` and `FIGHTS` data, the scoreboard headline, the
   "Before Round 2" ask, and the footer. The script computes the weighted scores and
   highlights the winner. Check that the headline matches what it computes.
3. Load the `artifact-design` skill if it's available, then publish with the `Artifact` tool
   (icon: `chat`). On later rounds, republish the same file so the link stays the same.
4. Reply in chat with: the link, the one-line result, and the founder question. Put the
   detail in the page, not the chat.

## Guard rails

- The footer always says the advisors are simulations and are not the real people, do not
  speak for them, and none of them is affiliated with this council.
- Anything that touches selling shares, loans, taxes or contracts gets a "confirm with your
  attorney/CPA" line on the page. In the US, selling shares to friends and family is still a
  securities offering and needs an exemption (federal and state). Flag it, but don't give it
  as legal advice.
- When the founder's own documents contain a math or structure problem (e.g. a profit share
  split only among the shares actually sold), the council has to raise it in Round 1.
