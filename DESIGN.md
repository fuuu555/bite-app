---
name: BiteMap
description: Warm, map-first restaurant discovery for everyday use in Taiwan.
colors:
  canvas: "#f6f4ee"
  surface: "#ffffff"
  surface-muted: "#eeece5"
  ink: "#142b32"
  ink-muted: "#5d6d71"
  hairline: "#d9ddd9"
  action-coral: "#f26b4f"
  action-coral-hover: "#d9553b"
  map-water: "#b9ded7"
typography:
  headline:
    fontFamily: "Geist, Noto Sans TC, sans-serif"
    fontSize: "2.15rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.04em"
  title:
    fontFamily: "Geist, Noto Sans TC, sans-serif"
    fontSize: "1.3rem"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "-0.025em"
  body:
    fontFamily: "Geist, Noto Sans TC, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.75
  label:
    fontFamily: "Geist, Noto Sans TC, sans-serif"
    fontSize: "0.82rem"
    fontWeight: 650
    lineHeight: 1.4
rounded:
  sm: "8px"
  md: "14px"
  lg: "22px"
  pill: "999px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "18px"
  lg: "28px"
components:
  button-primary:
    backgroundColor: "{colors.action-coral}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    height: "44px"
    padding: "0 18px"
  map-search:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.surface}"
    rounded: "{rounded.pill}"
    height: "44px"
    padding: "0 17px"
  preview-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "20px"
---

# Design System: BiteMap

## Overview

**Creative North Star: "The Friendly City Map"**

BiteMap is a practical cartographic interface with a warm, approachable surface. The map remains the main content; controls float above it as compact tools rather than turning the screen into a dashboard. Warm paper neutrals reduce glare, deep blue-green ink provides authority, and coral marks the next useful action.

The system is quiet and information-first. It uses clear Traditional Chinese labels, consistent Tabler line icons, and concise feedback so users can understand location and search state without studying the interface.

**Key Characteristics:**

- Map-first composition with restrained overlays.
- Warm neutral surfaces and one scarce coral action color.
- Rounded controls with soft, ambient depth.
- Desktop and mobile share one visual language and reflow deliberately.

## Colors

The palette combines warm paper neutrals with deep blue-green text and a coral action accent; cuisine colors are data, not decoration.

### Primary

- **Action Coral:** Calls attention to the active destination, primary actions, and the BiteMap mark.

### Neutral

- **Warm Canvas:** The default application background and loading surface.
- **Clean Surface:** Cards, controls, and navigation surfaces above the map.
- **Deep Map Ink:** Primary text and high-emphasis controls.
- **Quiet Ink:** Supporting copy, status text, and inactive navigation.
- **Soft Hairline:** Low-contrast boundaries between interactive surfaces.

**The One Coral Rule.** Coral identifies one active route or next action at a time; cuisine colors must not compete with navigation state.

## Typography

**Display Font:** Geist (with Noto Sans TC and sans-serif fallback)  
**Body Font:** Geist (with Noto Sans TC and sans-serif fallback)

**Character:** The current product uses a neutral, compact sans-serif hierarchy. Distinction comes from weight, scale, and spacing rather than decorative lettering.

### Hierarchy

- **Headline:** Bold, tightly tracked headings for page-level messages.
- **Title:** Compact restaurant and panel titles.
- **Body:** Comfortable explanatory text with generous line height and a maximum measure near 54–68 characters.
- **Label:** Semibold compact text for controls, navigation, cuisine, and system state.

**The Plain-Language Rule.** Controls name the action in Traditional Chinese; status text states the current condition and, on failure, the available recovery.

## Layout

Public pages reserve a fixed bottom band for five equal navigation targets. The map fills the remaining dynamic viewport, while brand, search state, location control, and restaurant preview sit in predictable screen-edge zones. Desktop constrains the navigation content to 720px and places the restaurant preview at the lower left. Below 768px, navigation becomes icon-over-label, controls tighten to 10px edge insets, and the preview expands between both screen edges above the Footer.

Spacing follows an 8–12–18–28px rhythm. Related label and value pairs stay close; separate tasks receive the larger intervals.

## Elevation & Depth

The interface is flat by default and uses soft ambient shadows only where a control must remain legible over map detail. Panels use a broader, lower-opacity shadow; compact controls use a smaller shadow. Hairline borders keep white-on-map surfaces defined without heavy outlines.

**The Map Stays Behind Rule.** Depth separates controls from geographic content, never creates ornamental floating card stacks.

## Shapes

Controls use gently rounded 8px corners, floating map panels use 14px, and the restaurant preview uses a softer 22px silhouette. Search uses a pill only because it is a transient map action. Map pins and the BiteMap mark share the rotated teardrop silhouette.

## Components

### Buttons

- **Primary:** Coral fill, white text, 44px minimum height, and an 8px radius.
- **Map Search:** Deep ink pill centered above the map; it appears only after the visible area changes.
- **Hover / Focus:** Darken or shift the surface slightly; always preserve a visible keyboard focus treatment.
- **Disabled:** Retain the component silhouette and reduce opacity while changing the cursor.

### Cards / Containers

- **Corner Style:** 14px for utility panels and 22px for the restaurant preview.
- **Background:** Opaque or nearly opaque white so map labels do not interfere with text.
- **Shadow Strategy:** Ambient shadow plus a soft hairline border.
- **Internal Padding:** 18–20px for compact public surfaces.

### Navigation

The Footer always contains Explore, Map, Meal, Chat, and Profile in that order. Every item combines a Tabler icon and a text label. The active item uses deep text, a coral icon, and a short top indicator so state is not communicated by color alone. Mobile targets divide the available width equally and include safe-area padding.

### Map Marker

Single-store markers use the restaurant's primary cuisine color and a visible first-character label. A white border and soft shadow preserve contrast against the map; the accessible name includes both restaurant and cuisine.

### Restaurant Preview

The preview shows cuisine, restaurant name, price range, close action, and one detail link. It sits above the Footer and replaces lower map controls on mobile to avoid overlap.

## Do's and Don'ts

### Do:

- **Do** keep the map visible and make overlays compact.
- **Do** pair cuisine color with readable text or an icon.
- **Do** retain old map results while a new visible-area query is running or fails.
- **Do** use Tabler icons at a consistent stroke weight.

### Don't:

- **Don't** add dashboard cards, metrics, or promotional content to the public map.
- **Don't** use coral for passive decoration or cuisine data.
- **Don't** hide active, loading, empty, or failure state behind icon-only feedback.
- **Don't** add 3D map pitch or buildings to the current 2D map experience.
