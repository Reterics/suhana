import { useEffect } from 'preact/hooks';

export default function PrivacyPage() {
  useEffect(() => {
    document.title = 'Privacy • Suhana';
  }, []);

  return (
    <div className="flex-1 flex flex-col items-center justify-start p-8 text-left overflow-y-auto">
      <div className="w-full max-w-3xl bg-white border border-gray-200 rounded-lg shadow-sm p-6">
        <div className="flex items-center gap-3 mb-4">
          <img src="./suhana.png" className="h-8 w-auto" alt="Suhana logo" />
          <h1 className="text-2xl font-bold text-gray-900">Privacy</h1>
        </div>

        <p className="text-sm text-gray-600 mb-4">
          This page explains how Suhana actually handles your data on-device and, when you
          choose a cloud model, what leaves your machine. You can change these behaviors in
          Settings at any time.
        </p>

        <div className="space-y-4 text-sm text-gray-700">
          <section>
            <h2 className="text-base font-semibold text-gray-900">What gets processed</h2>
            <ul className="list-disc list-inside space-y-1">
              <li>
                Your chat prompts and the assistant responses are processed to generate
                answers.
              </li>
              <li>
                If you select a local backend (Ollama), processing stays on your device.
              </li>
              <li>
                If you select a cloud backend (e.g., OpenAI, Gemini, Claude), your prompts
                and necessary context are sent to that provider to obtain a response, per
                their terms.
              </li>
              <li>
                Optional voice features transcribe audio locally if Whisper is available;
                otherwise, no audio is sent anywhere by default.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900">Storage and retention</h2>
            <ul className="list-disc list-inside space-y-1">
              <li>
                Conversation history is stored in the configured database via
                ConversationStore. By default this is a local SQLite file (suhana.db) in
                the app directory. You can switch to Postgres or MongoDB in settings.
              </li>
              <li>
                Starting a chat from the welcome screen without an API key uses a shared
                guest identity ("guest_public"). Those conversations are persisted by
                default unless you turn off "Store conversation history" in Settings.
              </li>
              <li>
                Using the “Guest Login” API creates a temporary guest user with more
                restrictive defaults (history not stored, analytics disabled) unless you
                change them.
              </li>
              <li>
                Local artifacts may be written to these folders/files: logs/ (runtime
                logs), vectorstore/ (embeddings index), memory/ (long‑term memory),
                knowledge/ (your added docs), settings.json and profile.json (preferences
                and profile). These stay on your machine.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900">Transport & security</h2>
            <ul className="list-disc list-inside space-y-1">
              <li>
                API access uses keys you control. Keys are stored in your local database
                and can be revoked at any time.
              </li>
              <li>
                Streaming can be enabled. There is also an optional secured streaming mode
                that establishes a client key and streams AES‑GCM encrypted chunks from the
                server to the client.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900">Analytics & sharing</h2>
            <ul className="list-disc list-inside space-y-1">
              <li>
                Suhana does not bundle third‑party analytics in the app UI. A local
                "Allow usage analytics" toggle controls whether usage metrics may be
                recorded locally; when off, Suhana avoids collecting usage metrics.
              </li>
              <li>
                "Share conversations" controls if your conversations may be shared with
                other users on the same server instance. It is off by default.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-base font-semibold text-gray-900">Your choices</h2>
            <ul className="list-disc list-inside">
              <li>Use local LLMs via Ollama to keep processing entirely on-device.</li>
              <li>Switch off "Store conversation history" to minimize persistence.</li>
              <li>Use secured streaming when sharing a screen or network you don’t trust.</li>
              <li>Review and adjust privacy options in Settings at any time.</li>
            </ul>
          </section>
        </div>

        <div className="mt-6 flex items-center justify-between text-sm">
          <a href="#/" className="underline text-gray-700">Back</a>
          <a href="#/" className="bg-black text-white px-3 py-1 rounded">Start chatting</a>
        </div>
      </div>
    </div>
  );
}
