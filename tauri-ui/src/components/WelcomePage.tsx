import { useRef, useState } from "preact/hooks";
import { motion } from "motion/react";
import {SendHorizontal, Settings} from "lucide-preact";
import Microphone from "../assets/microphone.svg?react"

type WelcomeProps = {
  setGuestMode: (v: boolean) => void;
  setInitialInput?: (text: string) => void;
  examplePrompts?: string[];
};

export default function WelcomeScreen({
  setGuestMode,
  setInitialInput,
  examplePrompts = [
    "Generate unit tests for my React hook",
    "Why is my Docker build slow?",
  ],
}: WelcomeProps) {
  const [value, setValue] = useState("");

  const barRef = useRef<HTMLDivElement>(null);
  const logoRef = useRef<HTMLImageElement>(null);
  const [animating, setAnimating] = useState(false);
  const [targetCoords, setTargetCoords] = useState<{
    input: {
      x: number; y: number;
    },
    logo: {
      x: number; y: number;
    }
  } | null>({
    input: { x: 0, y: 0 },
    logo: { x: 0, y: 0 },
  });

  const startChat = async (prompt?: string) => {
    if (animating) return;
    const sanitizedPrompt = prompt?.trim() || '';
    setInitialInput?.(sanitizedPrompt);
    setValue(sanitizedPrompt);

    const bar = barRef.current;
    const logo = logoRef.current;
    if (typeof window !== "undefined" && bar && logo && typeof bar.getBoundingClientRect === "function") {
      const barRect = bar.getBoundingClientRect();
      const logoRect = logo.getBoundingClientRect();

      setTargetCoords({
        input: {
          x: -barRect.left,
          y: Math.max(0, window.innerHeight - barRect.bottom + 42),
        },
        logo: {
          x: -logoRect.left,
          y: -logoRect.top,
        },
      });
      setAnimating(true);
      return false; // proceed happens on animation complete
    }

    setGuestMode(true);
    return true
  };

  return (
    <div
      className="flex-1 flex flex-col items-center justify-center p-8 text-center select-none"
      role="button"
      tabIndex={0}
      aria-label="Start chat"
    >
      <motion.img
        ref={logoRef}
        src="./suhana.png"
        className="h-24 w-auto mb-6 pointer-events-none"
        alt="Suhana logo"
        loading="lazy"
        decoding="async"
        initial={{ x: 0, y: 0, width: "96px", height: "auto" }}
          animate={
            animating
              ? { x: targetCoords?.logo.x, y: targetCoords?.logo.y, width: "12px" }
              : { x: 0, y: 0, width: "96px" }
          }
        transition={{ duration: 0.5, ease: "easeInOut" }}
      />

      <motion.h1
        className="text-3xl font-bold text-black mb-2 pointer-events-none"
        initial={{ opacity: 1 }}
        animate={{ opacity: animating ? 0 : 1 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
      >
        Welcome to Suhana
      </motion.h1>
      <motion.p
        id="welcome-help"
        initial={{ opacity: 1 }}
        animate={{ opacity: animating ? 0 : 1 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="text-base text-gray-500 max-w-xl mb-22 leading-relaxed pointer-events-none"
      >
        Your intelligent assistant for development and conversation.
      </motion.p>

      <div
        className="w-full max-w-xl text-left"
        // keep inner controls clickable without triggering the big CTA unless they want to
        onClick={(e) => e.stopPropagation()}
      >
        <motion.div
          initial={{ opacity: 1 }}
          animate={{ opacity: animating ? 0 : 1 }}
          transition={{ duration: 0.4, ease: "easeOut" }}
          className="flex flex-wrap gap-2 mb-2 px-3 justify-center"
        >
          {examplePrompts.map((p) => (
            <button
              key={p}
              type="button"
              className="text-sm rounded-full border border-zinc-300 px-3 py-1 text-gray-700 hover:bg-neutral-100 transition"
              onClick={(e) => {
                e.stopPropagation(); // prevent big CTA
                void startChat(p);
              }}
              disabled={animating}
              title={p}
            >
              {p}
            </button>
          ))}
        </motion.div>

        <motion.div
          ref={barRef}
          initial={{ x: 0, y: 0, width: "100%", borderRadius: 12 }}
          animate={
            animating
              ? { x: targetCoords?.input.x, y: targetCoords?.input.y, width: "100vw", borderRadius: 0 }
              : { x: 0, y: 0, width: "100%", borderRadius: 12 }
          }
          transition={{ duration: 0.5, ease: "easeInOut" }}
          onAnimationComplete={async () => {
            if (animating) {
              setAnimating(false);
              setGuestMode(true);
            }
          }}
          style={{ willChange: "width" }}
        >
          <form className="relative p-3 space-y-1 [transform:none]">
            <textarea
              rows={2}
              id="guest-input"
              placeholder="Ask anything to start a guest chat…"
              value={value}
              onKeyUp={(e) => setValue((e.currentTarget as HTMLTextAreaElement).value)}
              inputMode="text"
              aria-describedby="welcome-help"
              className="w-full border border-gray-300 rounded px-3 py-2 bg-neutral-50
                       shadow-sm focus:outline-none focus:ring-1 focus:ring-black"
              disabled={animating}
              onFocus={(e) => {
                // allow focusing/caret, but jump into chat
                // stop bubbling to container (already focused)
                e.stopPropagation();
                void startChat(value);
              }}
            />

            <div className="flex items-center justify-between transition-all duration-300 ease-in-out min-h-8">
              <div className="flex items-center gap-3">
                <button
                  title="Microphone"
                  onClick={(e) => {
                    e.stopPropagation();
                    void startChat(); // go into chat where mic lives
                  }}
                  disabled={animating}
                >
                  <Microphone className="h-5 w-5 hover:text-black" />
                </button>

                <button
                  title="Settings"
                  onClick={(e) => {
                    e.stopPropagation();
                    void startChat(); // or open a settings modal instead
                  }}
                  disabled={animating}
                >
                  <Settings className="h-5 w-5 hover:text-black" />
                </button>
              </div>

              <div className="flex items-center gap-3 text-gray-500">
                <button
                onClick={(e) => {
                  e.stopPropagation();
                  void startChat(value);
                }}
                className="text-white bg-black p-2 rounded hover:bg-gray-800"
                disabled={animating}
                title="Send"
              >
                <SendHorizontal className="h-4 w-4" />
              </button>
              </div>
            </div>
          </form>
        </motion.div>

        <motion.p
          initial={{ opacity: 1 }}
          animate={{ opacity: animating ? 0 : 1 }}
          transition={{ duration: 0.4, ease: "easeOut" }}
          className="mt-1 text-xs text-gray-400 px-3 text-center"
        >
          By starting a guest chat, you agree to basic processing for quality and safety.{" "}
          <a
            href="/privacy"
            className="underline"
            onClick={(e) => {
              // allow following the link without triggering the big CTA
              e.stopPropagation();
            }}
          >
            Privacy
          </a>
          .
        </motion.p>
      </div>
    </div>
  );
}
