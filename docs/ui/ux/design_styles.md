# Design styles you need to know:

These are the visual languages dominating right now. When you reference them in your FRONTEND_GUIDELINES.md or in prompts to AI, these terms unlock specific, recognizable aesthetics instead of vague descriptions.

# Glassmorphism

frosted glass effect. Translucent elements with background blur, subtle borders, and soft shadows floating over colorful backgrounds. Think Apple's macOS, Windows 11, Spotify's mobile app. Use backdrop-filter: blur() in CSS. Creates depth and hierarchy without heavy shadows. Looks premium. Works great for cards, modals, navigation bars, and dashboards. The risk: transparency can reduce readability, so keep text contrast high.

# Neobrutalism

raw, bold, intentionally unpolished. High-contrast colors, thick black borders, flat shadows, clashing palettes, quirky fonts. Think Gumroad, early Notion vibes. It's minimalism with attitude. Works well for creative brands, portfolios, indie tools. Stands out because everything else looks the same. Tell AI: "neobrutalist style with thick borders and bold primary colors."

# Neumorphism (Soft UI)

elements look like they're extruded from or pressed into the background. Soft, diffused shadows on both sides create a tactile, 3D feel. Subtle and elegant but tricky for accessibility because low contrast can make buttons hard to distinguish. Works best for small UI elements, toggles, sliders, cards. Not great as your entire design language.

# Bento grid

modular layouts where content is arranged in blocks of different sizes, like a Japanese bento box. Apple popularized this. Cards of varying dimensions create visual rhythm and hierarchy. Big cards for important content, smaller cards for secondary information. Responsive by nature because the grid rearranges on mobile. Perfect for dashboards, product pages, feature showcases, portfolios. This is probably the most practical trend to learn because it solves real layout problems.

# Dark mode

not just a preference toggle anymore, it's a design system. Dark backgrounds with light text, careful contrast ratios, and muted accent colors. Reduces eye strain, saves battery on OLED screens, and looks premium. If you're building any consumer app, plan for both light and dark mode from the start. Don't add it on randomly later. Define both palettes and themes in your FRONTEND_GUIDELINES.md.

# Kinetic typography

text that moves, stretches, reacts to scroll or cursor. Headlines that animate on entry, text that scales as you scroll, and interactive type treatments. Not just fade-ins. With modern CSS and libraries like Framer Motion, this is achievable without heavy JavaScript. Use sparingly for hero sections and key moments when applicable design wise.

# Micro-interactions

small animations that respond to user actions. A button that subtly scales on hover. A checkbox that bounces when clicked. A loading spinner that feels alive. These tiny details separate polished products from truly amateur ones. They communicate that the interface is responsive and alive and premium. Framer Motion and CSS transitions handle these easily.

**When you're prompting AI, don't say "make it look modern." Say "glassmorphism cards with bento grid layout, dark mode, and micro-interactions on hover states." That's a specific, buildable direction.**
**Lock your design decisions in FRONTEND_GUIDELINES.md before coding starts. Pick one or two of these styles, define your color palette, spacing scale, border radius, shadow values, and animation timing, and AI will follow them consistently if they're documented solidly. If they're not documented, every component will look different and there will be ZERO consistency**
