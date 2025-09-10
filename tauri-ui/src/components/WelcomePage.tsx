import { useRef, useState } from "preact/hooks";

type WelcomeProps = {
  handleSendMessage: (text: string) => Promise<void> | void;
  setGuestMode: (v: boolean) => void;
  navigateToChat?: () => void; // call when first message is sent or when entering chat
  examplePrompts?: string[];
};

export default function WelcomeScreen({
  handleSendMessage,
  setGuestMode,
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

  /** Core start logic */
  const startChat = async (prompt?: string) => {
    if (submitting) return;
    try {
      setSubmitting(true);
      setGuestMode(true);

      // If a prompt is provided, send it as the first message,
      // otherwise just navigate to the empty chat.
      if (prompt && prompt.trim()) {
        await handleSendMessage(prompt.trim());
      }

      navigateToChat?.();
      setValue("");
    } finally {
      setSubmitting(false);
    }
  };

  /** Whole-page CTA: click/tap anywhere to jump into chat (no prompt) */
  const onBigCtaClick = () => {
    void startChat();
  };

  /** Keyboard access for the big CTA area */
  const onBigCtaKeyDown: preact.JSX.KeyboardEventHandler<HTMLDivElement> = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      void startChat();
    }
  };

  /** Submit from the form/input */
  const onSubmit: preact.JSX.GenericEventHandler<HTMLFormElement> = (e) => {
    e.preventDefault();
    if (isComposing) return;
    e.stopPropagation(); // don't bubble to the big CTA
    void startChat(value);
  };

  return (
    <div
      className="flex-1 flex flex-col items-center justify-center p-8 text-center select-none"
      role="button"
      tabIndex={0}
      onClick={onBigCtaClick}
      onKeyDown={onBigCtaKeyDown}
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
        {/* Example prompt chips */}
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
              disabled={submitting}
              title={p}
            >
              {p}
            </button>
          ))}
        </div>

        {/* Form: input (Enter submits) */}
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
            disabled={submitting}
            // Clicking the input should also go to chat instantly (big CTA UX):
            onFocus={(e) => {
              // allow focusing/caret, but jump into chat
              // stop bubbling to container (already focused)
              e.stopPropagation();
              void startChat();
            }}
          />
        </form>

        {/* Secondary controls */}
        <div className="mt-4 flex items-center justify-between text-gray-500 text-sm">
          <div className="flex items-center gap-3">
            <button
              title="Microphone"
              onClick={(e) => {
                e.stopPropagation();
                void startChat(); // go into chat where mic lives
              }}
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
                <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"></path>
                <circle cx="12" cy="12" r="3"></circle>
              </svg>
            </button>
          </div>

          <button
            onClick={(e) => {
              e.stopPropagation();
              void startChat(value || "Hello");
            }}
            className="text-white bg-black px-3 py-2 rounded hover:bg-gray-800 disabled:opacity-50"
            disabled={submitting}
            title="Send"
          >
            Start
          </button>
        </div>

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
