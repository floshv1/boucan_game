import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}", "./components/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        // Core arcade palette (see globals.css for the documented scale).
        ink: "#15102A",
        panel: "#271A45",
        panel2: "#33235C",
        buzz: "#FF2E63",
        buzzdeep: "#C0103A",
        volt: "#C6FF4A",
        cream: "#FBF4E6",
        muted: "#9A87C4",
        // Quiz answer tiles — one stable colour per slot, used on BOTH the player
        // phone and the TV so a given answer reads as the same colour everywhere.
        // Tuned to the brand (pink / teal / lime / amber) instead of raw Tailwind.
        "quiz-a": "#FF2E63",
        "quiz-b": "#2BD9D9",
        "quiz-c": "#C6FF4A",
        "quiz-d": "#FFB23E",
      },
      fontFamily: {
        display: ["var(--font-display)", "system-ui", "sans-serif"],
        body: ["var(--font-body)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      // Named display sizes so headlines stop being ad-hoc text-[22vw] / text-6xl.
      // Body text keeps Tailwind's default scale.
      fontSize: {
        "display-hero": ["clamp(4rem, 22vw, 8rem)", { lineHeight: "0.8", letterSpacing: "0" }],
        "display-2xl": ["clamp(2.75rem, 8vw, 4.5rem)", { lineHeight: "0.95" }],
        "display-xl": ["clamp(2rem, 5vw, 3rem)", { lineHeight: "1" }],
      },
      // Arcade 3D "press" shadows — tokenised so the depth colour stays consistent
      // (these used to be copy-pasted magic hex in Button/globals/home).
      boxShadow: {
        "arcade-volt": "0 6px 0 0 #9BBF00",
        "arcade-volt-press": "0 2px 0 0 #9BBF00",
        "arcade-buzz": "0 6px 0 0 #8E0C2C",
        "arcade-buzz-press": "0 2px 0 0 #8E0C2C",
        "arcade-deep": "0 6px 0 0 #5A0518",
        "arcade-deep-press": "0 2px 0 0 #5A0518",
      },
      keyframes: {
        // TV reveal: the correct answer flashes to draw the room's eye.
        "reveal-flash": {
          "0%": { boxShadow: "0 0 0 0 rgba(198,255,74,0)" },
          "30%": { boxShadow: "0 0 0 6px rgba(198,255,74,0.6)" },
          "100%": { boxShadow: "0 0 0 3px rgba(198,255,74,0.35)" },
        },
        // TV podium: each step rises into place.
        "podium-rise": {
          "0%": { transform: "translateY(24px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
      },
      animation: {
        "reveal-flash": "reveal-flash 600ms ease-out forwards",
        "podium-rise": "podium-rise 460ms cubic-bezier(0.22,1,0.36,1) both",
      },
    },
  },
  plugins: [],
};

export default config;
