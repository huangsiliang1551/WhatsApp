# H5 Growth App Redesign Spec

## Summary

This redesign reframes the current H5 experience as a single-purpose growth product: a task-and-earn app with a clear execution path.

The current issue is not a lack of features. The issue is that too many features compete at the same level, making the experience feel like a stitched-together H5 rather than a mature mobile product.

The v1 redesign goal is to make the product feel like a credible, growth-oriented app by simplifying the information hierarchy, strengthening the task completion loop, and moving support features into the right secondary positions.

The selected direction is:

- Product type: `growth-oriented task earnings app`
- Primary path: `see earning opportunity -> start task -> complete task -> confirm earnings -> decide whether to withdraw`
- Tone: energetic but controlled
- Visual principle: growth atmosphere with operational discipline, not noisy campaign-page styling

## Design Goals

- Make the first 5 seconds of the home experience obvious and conversion-driven
- Reduce decision fatigue when users enter the app
- Strengthen the perceived link between action and earnings
- Increase trust in wallet and withdrawal behaviors
- Make the product feel like one coherent app instead of a collection of utility pages
- Ensure the layout works across multiple language lengths and international audiences

## Non-Goals

- No H5 template market revival
- No multi-template productization
- No major backend capability redesign in this spec
- No large new gamification system that requires new business rules before launch
- No dependence on true WhatsApp production integration for this redesign

## Product Positioning

The H5 should be positioned internally and visually as a `task earnings app`, not a generic member portal and not an admin-like dashboard.

This means the experience should optimize for one dominant mental model:

`I come here to do tasks and see earnings progress`

Other capabilities remain important, but they should support that loop instead of competing with it:

- wallet confirms value
- profile handles account and trust
- support resolves problems
- leaderboard and promotions amplify motivation

## Primary Information Architecture

### Bottom Navigation

The primary navigation should be reduced to four tabs:

- `Home`
- `Tasks`
- `Earnings`
- `Me`

The current or historical secondary functions should not occupy first-level navigation:

- messages
- invite / promotion
- leaderboard
- tickets / support
- verification

Those should be relocated into the appropriate second-level surfaces.

### Page Responsibilities

#### Home

Role: `conversion and direction`

The Home page should answer four questions only:

- What can I earn today?
- What should I do next?
- What do I get when I complete it?
- If I have a problem, where do I go?

Home should function as a task command center, not a dashboard.

#### Tasks

Role: `execution`

The Tasks page should help users continue or start task work with minimal friction.

#### Earnings

Role: `value confirmation and trust`

The Earnings page should make money-related outcomes feel transparent, stable, and safe.

#### Me

Role: `account and service center`

The Me page should absorb account setup, messages, help, settings, verification, and promotional side paths.

## Home Page Redesign

## Home Page Objective

Home must become a single-thread experience. The top of the page should guide users through one flow:

`see earnings -> see current task -> tap primary CTA`

### Above-the-Fold Structure

The first screen should be limited to three layers:

1. `top status layer`
2. `earnings hero card`
3. `primary task action card`

It should not begin with grids of shortcuts, heavy leaderboard blocks, multiple competing cards, or support-heavy content.

### Top Status Layer

Purpose:

- establish account ownership
- feel like a real app home
- provide lightweight utility access

Content:

- avatar
- display name or masked account identity
- greeting or date context
- notification entry
- lightweight verification status if necessary

This area should be visually calm.

### Earnings Hero Card

This is the visual center of the home screen.

Recommended data points:

- `today's earnings`
- `withdrawable balance`
- `weekly progress toward target`

This card should feel like a blend of:

- asset summary
- progress motivation

It should not feel like a dense finance statement.

### Primary Task Action Card

This is the main behavioral driver of the page.

Only one dominant task card should be shown at a time, with at most one alternate task below it.

Required fields:

- task name
- current status
- estimated reward
- remaining steps or estimated completion time
- one clear primary CTA:
  - `Start now`
  - `Continue`
  - `Complete next step`

The purpose is to reduce user choice overload.

### Below-the-Fold Ordering

Below the first screen, modules should follow this order:

1. `in-progress tasks`
2. `recommended tasks`
3. `motivation / growth module`
4. `service and support entry`

This mirrors user intent more closely:

- finish what I already started
- see what else I can do
- get motivated
- ask for help if needed

### Content That Should Be Downgraded or Moved

These items should not occupy high visual priority on Home:

- large leaderboard sections
- large multi-entry shortcut grids
- announcement-heavy sections
- support-first blocks
- multiple equal-weight financial and operational cards shown together

They can remain in the product, but not in the primary decision zone.

## Tasks Page Redesign

The Tasks page should become the execution center.

### Task Grouping

The default grouping should be:

- `In Progress`
- `Available`
- `Completed`

The default landing state should open on `In Progress`.

Reason:
users entering Tasks are usually returning to continue something, not to study the entire catalog.

### Task Card Content

Each task card should remain concise and scannable:

- task name
- reward amount
- completion condition
- estimated time
- status
- primary button

Detailed rules and long descriptions should stay in the detail page, not the list.

### Task Detail Layout

The detail page should be structured into three sections:

1. `reward summary`
2. `completion steps`
3. `notes / support`

This improves comprehension and keeps users from getting lost in text.

## Earnings Page Redesign

The Earnings page should act as the trust layer.

Users should leave this page feeling:

- my earnings are real
- the records are clear
- the withdrawal path is understandable

### Recommended Structure

- `total and withdrawable balance`
- `today / week trend snapshot`
- `transaction history`
- `withdraw and recharge actions`

### Tone

Compared with Home, this page should feel calmer and more structured.

Home can carry growth momentum. Earnings must carry financial order and confidence.

## Me Page Redesign

The Me page should become the account and service center, not a dumping ground for leftover features.

### Recommended Content

- user information
- account and verification status
- WhatsApp binding status
- message center
- help and support
- settings
- invitation / promotion entry

This creates a familiar account-management pattern and reduces confusion around where service actions live.

## Motivation System

This redesign should use controlled motivation rather than aggressive promotion.

### Motivation Layers

#### Immediate Feedback

- instant task completion status
- immediate reward confirmation
- visible movement in progress indicators

#### Short-Cycle Goals

- daily target
- weekly target
- streak or consecutive completion marker

#### Competitive Amplifiers

- leaderboard
- rank movement
- limited competition prompts

Leaderboard should be an enhancer, not the core engine of engagement.

The true driver should remain:

`I am one step closer to the next earnings milestone`

## Visual Direction

The recommended visual direction is `controlled growth energy`.

### Principles

- strong but not noisy hero area
- clear card hierarchy
- sufficient spacing
- consistent icon and button language
- restrained motion

### Emotional Weight by Page

- `Home`: energetic and directive
- `Tasks`: clear and procedural
- `Earnings`: orderly and trustworthy
- `Me`: calm and service-oriented

The mature feel comes from a shared language with different emotional intensity by page, not from making every page look identical.

## Content and Copy Strategy

Copy should move away from generic system labels and backend-style buttons.

### Copy Rules

- short
- explicit
- action-oriented
- outcome-based

### Preferred Patterns

Instead of:

- `Submit`
- `Confirm`
- `Operation successful`

Prefer:

- `Start task now`
- `Continue task`
- `Estimated reward: XX`
- `Withdrawal request submitted`
- `One more step to completion`

This improves clarity and makes the product feel more intentional.

## Motion and Interaction Principles

- loading states should be fast and calm
- primary buttons should give strong feedback
- task completion can use light celebratory feedback
- avoid excessive modal interruptions
- avoid constant flashing, rotating banners, or noisy visual competition

The product should feel active, not chaotic.

## Internationalization and Language-Width Constraints

This is a first-class product constraint, not a polish task.

The H5 targets users across different countries, so the redesign must assume:

- different string lengths by language
- different line-break behaviors
- mixed Latin / Arabic / CJK content
- varying number, currency, and date formats
- potential right-to-left support in the future

### Layout Rules

- avoid fixed-width text containers for primary labels
- avoid visual designs that rely on one-line titles always fitting
- use flexible card layouts that allow two-line titles and subtitles without breaking alignment
- ensure CTA buttons can stretch or reflow for longer translated labels
- allow tab labels to scale without visual overlap
- avoid embedding critical copy into images
- prioritize icon + text pairings that still work when text grows by 30% to 100%

### Component Rules

- cards should tolerate two-line metric labels
- lists should support variable row heights when localized
- badges and pills should truncate gracefully only when non-critical
- empty states and help text should support longer wrapped paragraphs
- modal and bottom-sheet layouts should be checked for short and long languages

### Typographic Rules

- typography must remain readable for Latin, CJK, and mixed-script rendering
- line height should not be tuned so tightly that CJK looks cramped
- number groups, currencies, and dates should not assume one locale pattern

### Future RTL Readiness

RTL support does not need to ship in this phase, but the redesign should avoid patterns that make RTL impossible later.

That means:

- avoid left-dependent visual metaphors when unnecessary
- avoid asymmetric icon placement that breaks in mirrored layouts
- keep navigation and card structures logically reversible

## Priority Order for Delivery

This redesign should not be implemented as one giant visual rewrite.

Recommended delivery order:

1. `Home`
2. `Tasks`
3. `Bottom navigation`
4. `Earnings`
5. `Me`
6. `motivation polish and visual unification`

## Success Criteria

The redesign is successful if users can immediately understand:

- where to start
- what they are currently doing
- how they earn
- where to confirm value
- where to go for account or support issues

And if the product subjectively feels like:

- one coherent app
- a stable earning product
- a trustworthy mobile experience

not:

- a stitched H5
- a utility portal
- a campaign page made permanent

## Risks

### Over-energized Visuals

If the growth direction is pushed too far, the product may feel cheap or noisy rather than mature.

Mitigation:

- keep strong emphasis only in key places
- preserve spacing and hierarchy discipline
- keep wallet and service areas stable and restrained

### Home Overcrowding Regression

There will be pressure to re-add many modules to the first screen.

Mitigation:

- define Home as a task command center
- require secondary features to justify first-screen priority

### Localization Breakage

If the redesign is produced with short Chinese strings only, it will regress immediately in multilingual deployment.

Mitigation:

- require all redesigned modules to be checked against long localized strings
- test translated button, tab, card, and empty-state content before final acceptance

## Test and Validation Guidance

### UX Validation

- first-open comprehension review
- 5-second home impression review
- task start path review
- withdrawal confidence review

### Functional Validation

- Home can always drive the user into a task path
- Tasks clearly separate in-progress and available work
- Earnings clearly exposes withdrawable value and history
- Me consolidates support and account actions

### Localization Validation

- verify long English strings
- verify compact and dense CJK strings
- verify mixed-language content
- verify number and currency rendering
- verify that key CTAs remain usable when labels expand

## Final Recommendation

The product should be rebuilt as a `growth-oriented task command app`, not re-skinned as a prettier dashboard.

The redesign should prioritize:

- task clarity
- earnings feedback
- trust
- structured motivation
- multilingual resilience

That is the fastest route from the current half-finished H5 impression to a mature app impression.
