from ..config import agent_config
from ..app_state import AppState
from ..model import get_next_assistant_message, zip_messages
import difflib

MAX_RETRY = 1


def summarize_state_change(memory, prompt_recorder=None):
    old_state = AppState.previous_gui_state
    new_state = AppState.current_gui_state
    previous_action = memory.working_memory.previous_action

    diff_str = ''
    for line in difflib.unified_diff(old_state.describe_widgets_NL().splitlines(), new_state.describe_widgets_NL().splitlines(), fromfile=f'Previous ({old_state.activity})', tofile=f'Current ({new_state.activity})', lineterm=''):
        if line.startswith('@@'):
            continue
        diff_str += line + '\n'

    diff_str = diff_str.strip()

    if len(diff_str) == 0:
        if len(new_state.lost_messages) > 0:
            return f'''After the action, the following popup message(s) were shown and soon disappeared: {new_state.lost_messages}'''
        # return 'The screen is apparently the same as before the action.'
        return None

    system_message = f'''You are a helpful assistant who can interpret two consecutive Android GUI screens before and after a user's action and explain the result of the action to the user.'''

    user_messages = []
    assistant_messages = []

    popup_message = ''
    if len(new_state.lost_messages) > 0:
        popup_message = f'\nAfter the action, the following popup message(s) were shown and soon disappeared: {list(new_state.lost_messages)}'

    user_messages.append(f'''
Describe the result of the performed GUI action regarding the changes between previous and current screens. 

Guidelines:
- To describe a widget, use only one important property of the widget. 
- If previous action is expanding a collapsed widget or opening a navigation drawer, describe the widget that is expanded or opened. 
- Do not judge fail/pass of the action.
- There is at least one difference between the previous and current screens. Do NOT say like "there is no visible change."

- Performed GUI Action: {previous_action}

- Changes of widgets from the previous page to the current page:
"""
{diff_str}
"""{popup_message}

=== Below is the template for your answer ===
Action result summary: <Describe in 1~2 sentences.>
'''.strip())
    assistant_messages.append(get_next_assistant_message(system_message, user_messages, assistant_messages, model=agent_config.observer_model))

    state_change_summary = assistant_messages[-1].strip().removeprefix('Action result summary: ').strip()

    if prompt_recorder is not None:
        prompt_recorder.record(zip_messages(system_message, user_messages, assistant_messages), 'observe')

    return state_change_summary
