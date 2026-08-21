/** @type {import('tailwindcss').Config} */

// Classical design system, ported from
// `design_handoff_tribunal_ui/_ds/classical-.../styles.css`.
//
// Every value below points at the CSS variable declared in `src/index.css`, so
// the token block stays the single source of truth: retune a token there and
// both the utility classes and the component classes follow. Components must
// never hard-code a hex, a font name or a px value that lives here.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--color-bg)',
        surface: 'var(--color-surface)',
        ink: 'var(--color-text)',
        divider: 'var(--color-divider)',
        accent: {
          DEFAULT: 'var(--color-accent)',
          100: 'var(--color-accent-100)',
          200: 'var(--color-accent-200)',
          300: 'var(--color-accent-300)',
          400: 'var(--color-accent-400)',
          500: 'var(--color-accent-500)',
          600: 'var(--color-accent-600)',
          700: 'var(--color-accent-700)',
          800: 'var(--color-accent-800)',
          900: 'var(--color-accent-900)',
        },
        neutral: {
          100: 'var(--color-neutral-100)',
          200: 'var(--color-neutral-200)',
          300: 'var(--color-neutral-300)',
          400: 'var(--color-neutral-400)',
          500: 'var(--color-neutral-500)',
          600: 'var(--color-neutral-600)',
          700: 'var(--color-neutral-700)',
          800: 'var(--color-neutral-800)',
          900: 'var(--color-neutral-900)',
        },
        // Text at reduced presence. `--color-muted` is the system's
        // `color-mix(text 55%)`; `--color-body` its 80% card-body weight.
        muted: 'var(--color-muted)',
      },
      fontFamily: {
        heading: 'var(--font-heading)',
        body: 'var(--font-body)',
      },
      // Named for the role each size plays in the mockups, because the same
      // px value means different things and the design calls out roles, not
      // numbers. Line heights come from the handoff: 1.12 headings, 1.7-1.75
      // body.
      fontSize: {
        'display-lg': ['60px', { lineHeight: '1.12', letterSpacing: '-0.02em' }],
        display: ['52px', { lineHeight: '1.12', letterSpacing: '-0.02em' }],
        h2: ['30px', { lineHeight: '1.12', letterSpacing: '-0.015em' }],
        h3: ['24px', { lineHeight: '1.12', letterSpacing: '-0.015em' }],
        'h3-sm': ['23px', { lineHeight: '1.12', letterSpacing: '-0.015em' }],
        'card-title': ['19px', { lineHeight: '1.2' }],
        'card-title-sm': ['17px', { lineHeight: '1.2' }],
        lede: ['16px', { lineHeight: '1.72' }],
        base: ['15px', { lineHeight: '1.55' }],
        input: ['14px', { lineHeight: '1.7' }],
        statement: ['13.5px', { lineHeight: '1.75' }],
        'body-sm': ['13px', { lineHeight: '1.6' }],
        meta: ['12.5px', { lineHeight: '1.5' }],
        'meta-sm': ['12px', { lineHeight: '1.5' }],
        kicker: ['11px', { lineHeight: '1.4' }],
        'kicker-sm': ['10px', { lineHeight: '1.4' }],
      },
      spacing: {
        1: 'var(--space-1)',
        2: 'var(--space-2)',
        3: 'var(--space-3)',
        4: 'var(--space-4)',
        6: 'var(--space-6)',
        8: 'var(--space-8)',
      },
      borderRadius: {
        sm: 'var(--radius-sm)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
      },
      boxShadow: {
        sm: 'var(--shadow-sm)',
        md: 'var(--shadow-md)',
        lg: 'var(--shadow-lg)',
      },
      letterSpacing: {
        kicker: '0.1em',
        'kicker-wide': '0.14em',
        'kicker-wider': '0.16em',
        'kicker-widest': '0.18em',
      },
    },
  },
  plugins: [],
}
