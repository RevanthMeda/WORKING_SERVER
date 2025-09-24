# UI Consistency Audit Tracker

## Baseline Screens
- Engineering Dashboard (established layout / color tokens / interaction states)
- Report Generator (reference for typography scale, status chips, table density)

## Severity Legend
- **High** - Navigation, layout shell, or key workflow components break alignment.
- **Medium** - Visual styling (color, spacing, typography) inconsistent but functionality intact.
- **Low** - Minor iconography or microcopy deviations.

## Modules To Review
1. **Reports Notifications**
   - Capture desktop / tablet / mobile screenshots.
   - Note navigation/header alignment, card shells, alerts, and hover/focus behaviors.
   - Record severity + remediation notes in table below.

2. **I/O Builder**
   - Validate component density against baseline tables.
   - Confirm forms, modals, loaders reuse shared patterns.
   - Identify spacing, typography, and color drifts.

3. **Settings Configuration**
   - Ensure page shell matches dashboard (breadcrumbs, action buttons).
   - Check form controls, toggles, and feedback states.

4. **Account Management (Change Password)**
   - Align authentication flows with shared layout and form styling.
   - Check for consistent messaging and button hierarchy.

## Evidence Log
| Module | Viewport | Issue | Severity | Screenshot | Notes |
|--------|----------|-------|----------|------------|-------|
| Reports Notifications | Desktop | Standalone layout with bespoke gradients and nav inconsistent with dashboard | High | TODO/screenshots/notifications-desktop.png | Refactored to extend base layout, reuse page hero/module nav, and align cards with design-system tokens. |
| I/O Builder | Desktop | Gradient dashboard shell + custom nav diverged from baseline components | High | TODO/screenshots/io-builder-desktop.png | Converted to shared hero/nav, applied design-system palette, and reused card/btn primitives while retaining builder functionality. |
| System Settings | Desktop | Duplicate admin header/navigation and mismatched form styling | High | TODO/screenshots/system-settings-desktop.png | Adopted shared hero/navigation, normalized cards/toggles with design-system tokens, removed redundant footer. |
| Change Password | Desktop | Legacy neon theme with standalone layout and inconsistent typography | High | TODO/screenshots/change-password-desktop.png | Migrated to base layout with shared hero/nav, standardized form styling, and design-system tokens. |

## Action Items
- Populate evidence log with annotated images.
- Prioritize fixes (High before Medium/Low).
- Feed confirmed issues into implementation queue.
