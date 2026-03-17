---
name: senior-frontend
description: Comprehensive frontend development skill for building modern, performant web applications using ReactJS, NextJS, TypeScript, Tailwind CSS. Includes component scaffolding, performance optimization, bundle analysis, and UI best practices. Use when developing frontend features, optimizing performance, implementing UI/UX designs, managing state, or reviewing frontend code.
---

# Senior Frontend

Complete toolkit for senior frontend with modern tools and best practices.

## Quick Start

### Main Capabilities

This skill provides three core capabilities through automated scripts:

```bash
# Script 1: Component Generator
python scripts/component_generator.py [options]

# Script 2: Bundle Analyzer
python scripts/bundle_analyzer.py [options]

# Script 3: Frontend Scaffolder
python scripts/frontend_scaffolder.py [options]
```

## Core Capabilities

### 1. Component Generator

Automated tool for component generator tasks.

**Features:**
- Automated scaffolding
- Best practices built-in
- Configurable templates
- Quality checks

**Usage:**
```bash
python scripts/component_generator.py <project-path> [options]
```

### 2. Bundle Analyzer

Comprehensive analysis and optimization tool.

**Features:**
- Deep analysis
- Performance metrics
- Recommendations
- Automated fixes

**Usage:**
```bash
python scripts/bundle_analyzer.py <target-path> [--verbose]
```

### 3. Frontend Scaffolder

Advanced tooling for specialized tasks.

**Features:**
- Expert-level automation
- Custom configurations
- Integration ready
- Production-grade output

**Usage:**
```bash
python scripts/frontend_scaffolder.py [arguments] [options]
```

## Reference Documentation

### React Patterns

Comprehensive guide available in `references/react_patterns.md`:

- Detailed patterns and practices
- Code examples
- Best practices
- Anti-patterns to avoid
- Real-world scenarios

### Nextjs Optimization Guide

Complete workflow documentation in `references/nextjs_optimization_guide.md`:

- Step-by-step processes
- Optimization strategies
- Tool integrations
- Performance tuning
- Troubleshooting guide

### Frontend Best Practices

Technical reference guide in `references/frontend_best_practices.md`:

- Technology stack details
- Configuration examples
- Integration patterns
- Security considerations
- Scalability guidelines

## Tech Stack

**Languages:** TypeScript, JavaScript, Python, Go, Swift, Kotlin
**Frontend:** React, Next.js, React Native, Flutter
**Backend:** Node.js, Express, GraphQL, REST APIs
**Database:** PostgreSQL, Prisma, NeonDB, Supabase
**DevOps:** Docker, Kubernetes, Terraform, GitHub Actions, CircleCI
**Cloud:** AWS, GCP, Azure

## Development Workflow

### 1. Setup and Configuration

```bash
# Install dependencies
npm install
# or
pip install -r requirements.txt

# Configure environment
cp .env.example .env
```

### 2. Run Quality Checks

```bash
# Use the analyzer script
python scripts/bundle_analyzer.py .

# Review recommendations
# Apply fixes
```

### 3. Implement Best Practices

Follow the patterns and practices documented in:
- `references/react_patterns.md`
- `references/nextjs_optimization_guide.md`
- `references/frontend_best_practices.md`

## Best Practices Summary

### Code Quality
- Follow established patterns
- Write comprehensive tests
- Document decisions
- Review regularly

### Performance
- Measure before optimizing
- Use appropriate caching
- Optimize critical paths
- Monitor in production

### Security
- Validate all inputs
- Use parameterized queries
- Implement proper authentication
- Keep dependencies updated

### Maintainability
- Write clear code
- Use consistent naming
- Add helpful comments
- Keep it simple

## Common Commands

```bash
# Development
npm run dev
npm run build
npm run test
npm run lint

# Analysis
python scripts/bundle_analyzer.py .
python scripts/frontend_scaffolder.py --analyze

# Deployment
docker build -t app:latest .
docker-compose up -d
kubectl apply -f k8s/
```

## Troubleshooting

### Common Issues

Check the comprehensive troubleshooting section in `references/frontend_best_practices.md`.

### Getting Help

- Review reference documentation
- Check script output messages
- Consult tech stack documentation
- Review error logs

## Resources

- Pattern Reference: `references/react_patterns.md`
- Workflow Guide: `references/nextjs_optimization_guide.md`
- Technical Guide: `references/frontend_best_practices.md`
- Tool Scripts: `scripts/` directory

---

# Melonn Brand Design System

ALWAYS apply these guidelines when building or styling frontend UI for this project.

## Color Palette

### Primary Colors
| Token | Hex | Tailwind Class | Usage |
|---|---|---|---|
| Deep Purple | `#4929A1` | `melonn-purple` | Primary brand, headers, links, primary actions |
| Dark Navy | `#1A1659` | `melonn-navy` | All text on light backgrounds |
| Vibrant Green | `#00C97A` | `melonn-green` | CTAs, success states, positive indicators |

### Supporting Colors
| Token | Hex | Tailwind Class | Usage |
|---|---|---|---|
| Light Purple | `#9684E1` | `melonn-purple-light` | Hover states, secondary elements |
| Mint | `#74EBAE` | `melonn-mint` | Success backgrounds, highlights |
| Cyan | `#75E7EA` | `melonn-cyan` | Info states, data viz accents |
| Orange | `#FF802F` | `melonn-orange` | Warnings, attention |

### Tints (auto-generated)
| Token | Hex | Usage |
|---|---|---|
| `melonn-purple-50` | `#F0ECFA` | Light purple backgrounds |
| `melonn-purple-100` | `#E0D9F5` | Borders, input focus rings |
| `melonn-green-50` | `#E6FAF1` | Success backgrounds |
| `melonn-cyan-50` | `#E8FBFC` | Info backgrounds |
| `melonn-orange-50` | `#FFF3EB` | Warning backgrounds |
| `melonn-surface` | `#F3F3F3` | Page background |

## Tailwind CSS v4 Theme (globals.css)

```css
@theme inline {
  --color-melonn-purple: #4929A1;
  --color-melonn-purple-light: #9684E1;
  --color-melonn-purple-50: #F0ECFA;
  --color-melonn-purple-100: #E0D9F5;
  --color-melonn-navy: #1A1659;
  --color-melonn-navy-light: #2D2880;
  --color-melonn-green: #00C97A;
  --color-melonn-green-light: #74EBAE;
  --color-melonn-green-50: #E6FAF1;
  --color-melonn-mint: #74EBAE;
  --color-melonn-cyan: #75E7EA;
  --color-melonn-cyan-50: #E8FBFC;
  --color-melonn-orange: #FF802F;
  --color-melonn-orange-50: #FFF3EB;
  --color-melonn-surface: #F3F3F3;
  --font-heading: var(--font-lato);
  --font-body: var(--font-sora);
}
```

## Typography

- **Headings**: Lato, weight 700, `font-heading`
- **Body**: Sora, weight 400-600, `font-body`
- **Monospace**: Geist Mono (for logs, durations, code)
- Load via `next/font/google` in layout.tsx

### Scale
| Element | Font | Size | Weight | Color |
|---|---|---|---|---|
| Page Title | Lato | `text-xl` | 700 | `text-white` (on navy header) |
| Card Title | Lato | `text-sm` | 600 | `text-melonn-navy` |
| Body | Sora | `text-sm` | 400 | `text-melonn-navy` |
| Caption | Sora | `text-xs` | 400 | `text-melonn-navy/60` |
| Big Number | Lato | `text-3xl` | 700 | `text-melonn-navy` |

## Component Patterns

### Buttons
```html
<!-- Primary CTA -->
<button class="px-6 py-3 bg-melonn-green text-white font-semibold rounded-full
  hover:bg-melonn-green/90 disabled:bg-melonn-surface disabled:text-melonn-navy/40
  transition-colors font-heading">
  Analyze
</button>

<!-- Secondary -->
<button class="px-6 py-3 bg-white text-melonn-purple font-semibold rounded-full
  border-2 border-melonn-purple hover:bg-melonn-purple-50 transition-colors font-heading">
  Cancel
</button>

<!-- Ghost -->
<button class="px-4 py-2 text-melonn-purple font-medium rounded-lg
  hover:bg-melonn-purple-50 transition-colors text-sm">
  Show details
</button>
```

### Cards
```html
<div class="bg-white rounded-2xl border border-melonn-purple-50 shadow-sm p-5">
  <h3 class="text-sm font-semibold text-melonn-navy font-heading mb-3">Title</h3>
  <!-- Content -->
</div>
```

### Badges
```html
<!-- Brand -->
<span class="text-xs px-3 py-1 bg-melonn-purple-50 text-melonn-purple rounded-full font-medium">Shopify</span>
<!-- Success -->
<span class="text-xs px-3 py-1 bg-melonn-green-50 text-melonn-green rounded-full font-medium">High</span>
<!-- Warning -->
<span class="text-xs px-3 py-1 bg-melonn-orange-50 text-melonn-orange rounded-full font-medium">Medium</span>
<!-- Error -->
<span class="text-xs px-3 py-1 bg-red-50 text-red-600 rounded-full font-medium">Low</span>
```

### Inputs
```html
<input class="w-full px-4 py-3 border-2 border-melonn-purple-100 rounded-xl
  focus:outline-none focus:ring-2 focus:ring-melonn-purple/30 focus:border-melonn-purple
  text-melonn-navy placeholder:text-melonn-navy/40 font-body" />
```

### Score Indicators
- Score >= 70: `bg-melonn-green-50 text-melonn-green border-melonn-green/20`
- Score 40-69: `bg-melonn-orange-50 text-melonn-orange border-melonn-orange/20`
- Score < 40: `bg-red-50 text-red-600 border-red-200`

### Progress Bar
```html
<div class="h-1.5 bg-melonn-surface rounded-full overflow-hidden">
  <div class="h-full bg-gradient-to-r from-melonn-purple to-melonn-green rounded-full" />
</div>
```

## Semantic Color Mapping
| Semantic | Melonn Token |
|---|---|
| Success/OK | `melonn-green` / `melonn-green-50` |
| Warning | `melonn-orange` / `melonn-orange-50` |
| Error/Fail | `red-600` / `red-50` (keep standard red) |
| Info | `melonn-cyan` / `melonn-cyan-50` |
| Running/Active | `melonn-purple` / `melonn-purple-50` |
| Disabled/Skip | `melonn-navy/40` / `melonn-surface` |

## Layout Rules
- Page background: `bg-melonn-surface`
- Max content width: `max-w-5xl`
- Cards: `rounded-2xl`, nested elements: `rounded-xl`
- Buttons: `rounded-full` (pill shape)
- Results grid: `grid grid-cols-1 md:grid-cols-2 gap-4`
- Card padding: `p-5`
- Card gap: `gap-4`

## Do's
- Use `melonn-green` for all primary CTAs and positive indicators
- Use `melonn-purple` as the dominant brand color for headers and links
- Use `melonn-navy` for ALL text on light backgrounds
- Keep cards white with subtle `border-melonn-purple-50`
- Use pill shapes (`rounded-full`) for buttons and badges
- Use the gradient `from-melonn-purple to-melonn-green` sparingly for emphasis

## Don'ts
- Do NOT use `text-gray-*` for text -- use `text-melonn-navy` with opacity
- Do NOT use `bg-blue-600` for buttons -- use `melonn-green` or `melonn-purple`
- Do NOT use `rounded-lg` for cards -- use `rounded-2xl`
- Do NOT use dark mode -- light-mode only
- Do NOT use Geist font for UI text -- use Lato (headings) and Sora (body)
