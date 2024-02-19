from .types.gui_state import GUIState
from .utils.logger import Logger

from collections import defaultdict

logger = Logger(__name__)

class AppState:
    app_name = None
    activities = None
    visited_activities = defaultdict(lambda: 0)

    current_activity = None
    previous_activity = None
    current_gui_state = None
    previous_gui_state = None

    # To capture toast messages and popup messages that can be missed by the DroidBot-fetched GUI state
    temp_messages = []
    toasts = []

    @classmethod
    def initialize(cls, app_name, app_activities):
        cls.app_name = app_name
        cls.activities = app_activities

    @classmethod
    def set_current_gui_state(cls, droidbot_state):
        cls._set_current_gui_state(GUIState().from_droidbot_state(droidbot_state))
        app_activity_depth = cls.current_gui_state.get_app_activity_depth()
        if app_activity_depth != 0:
            logger.warning(f'App is not in the foreground. Current activity stack: {cls.current_gui_state.activity_stack}')

        cls.add_visited_activity(cls.current_gui_state.activity)
        
        # Check immediately captured temp messages are still visible
        for widget in cls.temp_messages:
            w = cls.current_gui_state.get_widget_by_signature(widget.signature)
            if w is None:
                cls.current_gui_state.lost_messages.add(widget.text)

        for message in cls.toasts:
            cls.current_gui_state.lost_messages.add(message)
        
        cls.temp_messages = []
        cls.toasts = []

    @classmethod
    def _set_current_gui_state(cls, gui_state):
        cls.previous_gui_state = cls.current_gui_state
        cls.current_gui_state = gui_state

    @classmethod
    def capture_temporary_message(cls, droidbot_state):
        gui_state = GUIState().from_droidbot_state(droidbot_state)

        _, appeared_widgets, _ = cls.current_gui_state.diff_widgets(gui_state)

        temp_message_count = 0
        for widget in appeared_widgets:
            if widget.text is not None and len(widget.text) > 0:
                cls.temp_messages.append(widget)
                temp_message_count += 1

                # we don't want to capture too many messages
                if temp_message_count > 3:
                    break

        return gui_state

    @classmethod
    def clear_temporary_message(cls):
        cls.temp_messages = []

    @classmethod
    def capture_toast_message(cls, captured_toast_messages):
        cls.toasts = captured_toast_messages

    @classmethod
    def add_visited_activity(cls, activity):
        # TODO: for the GUI-model-paired agent, we should also update the GUI states, transitions, etc.
        if activity not in cls.activities:
            # log warning
            return
        
        cls.visited_activities[activity] += 1
        cls.previous_activity = cls.current_activity if cls.current_activity is not None else activity
        cls.current_activity = activity

    @staticmethod
    def is_loading_state(droidbot_state):
        if len(droidbot_state.get_possible_input()) == 0:
            return True

        return False