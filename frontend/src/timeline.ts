import type { SignTimeline, SignWord } from "./types.ts";

// The fixed demo script (CLAUDE.md §5), pre-verified and cached so the live
// demo never depends on a flaky LLM call. The caption shows the English words;
// the avatar performs the gloss tokens. Frame counts are at FPS below and set
// the word timing — lexical signs get one beat, fingerspelled words get one
// beat per letter so "Jade" lingers while J-A-D-E is spelled.

const FPS = 30;
const BEAT = 26; // frames per lexical sign (~0.87s)
const LETTER = 16; // frames per fingerspelled letter (~0.53s)

const lex = (text: string, gloss: string, gesture: SignWord["gestures"][number]): SignWord => ({
  text,
  gloss: [gloss],
  frames: BEAT,
  gestures: [gesture],
});

/** Fingerspelled English word → one caption word, one fs cue per letter. */
const spell = (text: string): SignWord => {
  const letters = text.toUpperCase().replace(/[^A-Z]/g, "").split("");
  return {
    text,
    gloss: letters.map((l) => `fs:${l}`),
    frames: LETTER * letters.length,
    gestures: letters.map(() => "fingerspell" as const),
  };
};

export const DEMO_TIMELINE: SignTimeline = {
  fps: FPS,
  sentences: [
    {
      english: "Hello.",
      words: [lex("Hello", "HELLO", "wave")],
    },
    {
      english: "How are you doing today?",
      words: [
        lex("How", "HOW", "two-hands-up"),
        lex("are", "HOW", "two-hands-up"),
        lex("you", "YOU", "point-out"),
        lex("doing", "TODAY", "tap-down"),
        lex("today?", "TODAY", "tap-down"),
      ],
    },
    {
      english: "My name is Jade.",
      words: [
        lex("My", "MY", "point-self"),
        lex("name", "NAME", "name-tap"),
        lex("is", "NAME", "name-tap"),
        spell("Jade"),
      ],
    },
    {
      english: "I don't speak sign language, but my AI does.",
      words: [
        lex("I", "ME", "point-self"),
        lex("don't", "NOT", "tap-down"),
        lex("speak", "SIGN", "sign-sweep"),
        lex("sign", "SIGN", "sign-sweep"),
        lex("language,", "SIGN", "sign-sweep"),
        lex("but", "BUT", "but"),
        lex("my", "MY", "point-self"),
        spell("AI"),
        lex("does", "CAN", "can"),
      ],
    },
    {
      english: "I'm happy to communicate.",
      words: [
        lex("I'm", "ME", "point-self"),
        lex("happy", "HAPPY", "happy"),
        lex("to", "COMMUNICATE", "communicate"),
        lex("communicate", "COMMUNICATE", "communicate"),
      ],
    },
  ],
};

/** Flatten to the full ad-hoc utterance for a single continuous play-through. */
export function fullScriptSentence(timeline: SignTimeline) {
  return timeline.sentences.flatMap((s) => s.words);
}
