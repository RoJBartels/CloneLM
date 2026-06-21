# FontAwesome5 — LaTeX Icon Reference Guide

The **fontawesome5** LaTeX package provides access to the Font Awesome 5 icon
set from within LaTeX documents. It bundles a large collection of scalable
vector icons that can be embedded inline via dedicated LaTeX commands.

## Loading the package

Add `\usepackage{fontawesome5}` to your preamble. Each icon is then available
through a command, for example `\faGithub` renders the GitHub mark and
`\faCarSide` renders a car. Icons inherit the surrounding font size and color.

## Icon categories

The package groups its icons into several categories:

- **Brand logos** — company and product marks such as GitHub, Twitter,
  LinkedIn and YouTube. These are accessed with commands like `\faGithub`.
- **Tools and objects** — wrenches, gears, and other utility symbols, e.g.
  `\faWrench` and `\faCog`.
- **Currencies** — symbols for dollar, euro, and other currencies via commands
  such as `\faEuroSign`.
- **Vehicles** — cars, bicycles, planes and ships, e.g. `\faPlane`.

## Styles

Many icons are available in multiple styles: solid, regular, and brands.
The style is selected by an optional argument, for example
`\faHeart[regular]` for the outline heart versus `\faHeart` for the solid one.

## Finding social-media symbols

Social-media icons live in the *brands* style. To find a specific platform's
symbol, search the package documentation's brands table for the platform name;
the corresponding command is listed alongside a rendered preview of the icon.
