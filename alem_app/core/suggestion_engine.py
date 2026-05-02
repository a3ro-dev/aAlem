from PyQt6.QtCore import QObject, pyqtSignal, QThread
from alem_app.core.llm_router import LLMRouter
import config

class SuggestionWorker(QThread):
    suggestion_ready = pyqtSignal(str)

    def __init__(self, context: str, full_note: str):
        super().__init__()
        self.context = context
        self.full_note = full_note
        self.is_cancelled = False

    def run(self):
        try:
            app_config = config.config
            if not app_config.get("ai_suggestions_enabled", True):
                return
            if not app_config.get("groq_api_key", ""):
                return

            system_prompt = "You are a writing assistant. Complete the user's thought naturally. Output ONLY the completion text, no explanation, no quotes. Maximum 1-2 sentences."
            user_prompt = f"Note context:\n{self.full_note}\n\nComplete this: {self.context}"

            response = LLMRouter.complete(
                prompt=user_prompt,
                system=system_prompt,
                provider="groq",
                model="llama-3.1-8b-instant",
                stream=True
            )

            completion_text = ""
            for chunk in response:
                if self.is_cancelled:
                    return
                if chunk.choices and chunk.choices[0].delta.content:
                    completion_text += chunk.choices[0].delta.content

            if not self.is_cancelled and completion_text:
                self.suggestion_ready.emit(completion_text)

        except Exception as e:
            from alem_app.utils.logging import logger
            logger.error(f"Error in SuggestionWorker: {e}")


class SuggestionEngine(QObject):
    suggestion_ready = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None

    def request_suggestion(self, context: str, full_note: str):
        self.cancel()

        self._worker = SuggestionWorker(context, full_note)
        self._worker.suggestion_ready.connect(self.suggestion_ready.emit)
        self._worker.start()

    def cancel(self):
        if self._worker and self._worker.isRunning():
            self._worker.is_cancelled = True
            self._worker.quit()
            self._worker.wait()
            self._worker = None
