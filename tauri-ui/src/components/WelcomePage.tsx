import { useRef, useState } from "preact/hooks";
import { motion } from "motion/react";

type WelcomeProps = {
  setGuestMode: (v: boolean) => void;
  setInitialInput?: (text: string) => void;
  navigateToChat?: () => void; // optional external navigation handler
  examplePrompts?: string[];
};

export default function WelcomeScreen({
  setGuestMode,
  setInitialInput,
  navigateToChat,
  examplePrompts = [
    "Summarize this Git diff in plain English",
    "Generate unit tests for my React hook",
    "Why is my Docker build slow?",
  ],
}: WelcomeProps) {
  const [value, setValue] = useState("");
  const [isComposing, setIsComposing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const barRef = useRef<HTMLDivElement>(null);
  const [animating, setAnimating] = useState(false);
  const [dx, setDx] = useState(0);
  const [dy, setDy] = useState(0);
  const [pendingPrompt, setPendingPrompt] = useState<string | undefined>(undefined);

  const proceedStartChat = async (prompt?: string) => {
    if (submitting) return;
    try {
      setSubmitting(true);
      setGuestMode(true);

      setInitialInput?.(prompt?.trim() || '');

      navigateToChat?.();
      setValue("");
    } finally {
      setSubmitting(false);
    }
  };

  const startChat = async (prompt?: string) => {
    if (submitting || animating) return;

    // Measure the bottom block and compute translation to (x=0, bottom=16px)
    const el = barRef.current;
    if (typeof window !== "undefined" && el && typeof el.getBoundingClientRect === "function") {
      const rect = el.getBoundingClientRect();
      const targetBottomGap = 16; // px padding from bottom; set to 0 for flush
      const translateY = Math.max(0, window.innerHeight - rect.bottom - targetBottomGap);
      const translateX = -rect.left; // move left edge to x=0

      setDx(translateX);
      setDy(translateY);
      setPendingPrompt(prompt);
      setAnimating(true);
      return false; // proceed happens on animation complete
    }

    await proceedStartChat(prompt);
    return true
  };

  const onSubmit: preact.JSX.GenericEventHandler<HTMLFormElement> = (e) => {
    e.preventDefault();
    if (isComposing) return;
    e.stopPropagation();
    void startChat(value);
  };

  return (
    <div
      className="flex-1 flex flex-col items-center justify-center p-8 text-center select-none"
      role="button"
      tabIndex={0}
      aria-label="Start chat"
    >
      <img
        src="./suhana.png"
        className="h-24 w-auto mb-6 pointer-events-none"
        alt="Suhana logo"
        loading="lazy"
        decoding="async"
      />

      <h1 className="text-3xl font-bold text-black mb-2 pointer-events-none">Welcome to Suhana</h1>
      <p
        id="welcome-help"
        className="text-base text-gray-500 max-w-xl mb-6 leading-relaxed pointer-events-none"
      >
        Your intelligent assistant for development and conversation.
        <br />
        Try asking something below to start a guest chat.
      </p>

      <div
        className="w-full max-w-xl text-left"
        // keep inner controls clickable without triggering the big CTA unless they want to
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex flex-wrap gap-2 mb-4">
          {examplePrompts.map((p) => (
            <button
              key={p}
              type="button"
              className="text-sm rounded-full border border-zinc-300 px-3 py-1 text-gray-700 hover:bg-neutral-100 transition"
              onClick={(e) => {
                e.stopPropagation(); // prevent big CTA
                void startChat(p);
              }}
              disabled={submitting || animating}
              title={p}
            >
              {p}
            </button>
          ))}
        </div>

        <motion.div
          ref={barRef}
          initial={{ x: 0, y: 0, width: "100%", borderRadius: 12 }}
          animate={
            animating
              ? { x: dx, y: dy, width: "100vw", borderRadius: 0 }
              : { x: 0, y: 0, width: "100%", borderRadius: 12 }
          }
          transition={{ duration: 1, ease: "easeInOut" }}
          onAnimationComplete={async () => {
            if (animating) {
              setAnimating(false);
              await proceedStartChat(pendingPrompt);
            }
          }}
          style={{ willChange: "transform,width" }}
        >
          <form onSubmit={onSubmit} className="relative">
            <label htmlFor="guest-input" className="sr-only">
              Ask anything to start a guest chat
            </label>
            <input
              id="guest-input"
              ref={inputRef}
              type="text"
              placeholder="Ask anything to start a guest chat…"
              value={value}
              onChange={(e) => setValue((e.currentTarget as HTMLInputElement).value)}
              onCompositionStart={() => setIsComposing(true)}
              onCompositionEnd={() => setIsComposing(false)}
              inputMode="text"
              enterKeyHint="send"
              aria-describedby="welcome-help"
              className="w-full px-4 py-3 rounded-lg border border-zinc-300 bg-neutral-50 text-black
                       shadow-sm focus:outline-none focus:ring-2 focus:ring-black"
              disabled={submitting || animating}
              onFocus={(e) => {
                // allow focusing/caret, but jump into chat
                // stop bubbling to container (already focused)
                e.stopPropagation();
                void startChat();
              }}
            />
          </form>

          <div className="mt-4 flex items-center justify-between text-gray-500 text-sm">
            <div className="flex items-center gap-3">
              <button
                title="Microphone"
                onClick={(e) => {
                  e.stopPropagation();
                  void startChat(); // go into chat where mic lives
                }}
                disabled={submitting || animating}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-5 w-5 hover:text-black"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M12 19v3"></path>
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                  <rect x="9" y="2" width="6" height="13" rx="3"></rect>
                </svg>
              </button>

              <button
                title="Settings"
                onClick={(e) => {
                  e.stopPropagation();
                  void startChat(); // or open a settings modal instead
                }}
                disabled={submitting || animating}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-5 w-5 hover:text-black"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22-.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l-.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"></path>
                  <circle cx="12" cy="12" r="3"></circle>
                </svg>
              </button>
            </div>

            <button
              onClick={(e) => {
                e.stopPropagation();
                void startChat(value);
              }}
              className="text-white bg-black px-3 py-2 rounded hover:bg-gray-800 disabled:opacity-50"
              disabled={submitting || animating}
              title="Send"
            >
              Start
            </button>
          </div>
        </motion.div>

        <p className="mt-4 text-xs text-gray-400">
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
        </p>
      </div>
    </div>
  );
}
