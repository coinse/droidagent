from ..types.task import Task
from ..types.action import Action
from ..config import agent_config

from ..utils.stringutil import add_period, remove_period

import time
import re

class WorkingMemory:
    def __init__(self, task=None):
        self.task = task
        self.steps = []
        self.previous_action = None

    def register_task(self, task: Task):
        self.task = task

    def add_step(self, step_description, page, step_type='ACTION'):
        if step_type == 'ACTION' and isinstance(step_description, Action):
            self.previous_action = step_description

        timestamp = time.strftime("%H:%M:%S", time.localtime())
        self.steps.append((step_description, step_type, timestamp, page))

    def stringify(self):
        if len(self.steps) == 0:
            return '<no interactions performed>'
        memory_str = ''
        for i, (entry, item_type, timestamp, page) in enumerate(self.steps):
            if isinstance(entry, Action):
                entry = entry.get_action_record_str()
            if item_type == 'CRITIQUE':
                continue # hide previous critiques to avoid bias
            
            memory_str += f'{timestamp}:{page}: [{item_type}] {entry}\n'
        
        return memory_str.strip()

    def to_dict(self):
        task_execution_entries = []

        for desc, item_type, timestamp, page in self.steps:
            task_execution_entries.append({
                'description': str(desc),
                'type': item_type,
                'timestamp': timestamp,
                'page': page
            })

        return {
            'task': self.task.summary,
            'task_end_condition': self.task.end_condition,
            'working_memory': task_execution_entries
        }

    def make_virtual_conversation(self):
        # This should be called when we need a next action from the LLM
        WM = list(enumerate(self.steps))
        
        user_messages_draft = []
        user_messages = []
        assistant_messages = []

        BASIC_FEEDBACK_MESSAGE = lambda page_change: f'I performed the action you suggested. What should be the next action?' if page_change is None else f'I performed the action you suggested. The page changed from {page_change[0]} to {page_change[1]}. What should be the next action?'

        prev_critique = None
        previous_item_type = None
        has_critique = False

        need_feedback_message = False

        for i, (entry, item_type, timestamp, page) in WM:
            if item_type == 'ACTION':
                if need_feedback_message:
                    user_messages_draft.append((BASIC_FEEDBACK_MESSAGE(None), prev_critique, page))
                    prev_critique = None
                if isinstance(entry, Action):
                    assistant_messages.append(entry.get_action_str())
                else:
                    assistant_messages.append(str(entry))
                need_feedback_message = True

            elif item_type == 'CRITIQUE':
                # append to the last observation
                if previous_item_type == 'OBSERVATION':
                    user_messages_draft[-1] = (user_messages_draft[-1][0], entry, user_messages_draft[-1][2])
                elif previous_item_type == 'ACTION':
                    prev_critique = entry
                has_critique = True
                
            elif item_type == 'OBSERVATION':
                assert previous_item_type == 'ACTION'
                user_messages_draft.append((f'''
I performed the action, and as a result, {entry[0].lower() + add_period(entry[1:])} What should be the next action?'''.strip(), None, page))

                need_feedback_message = False

            previous_item_type = item_type

        if need_feedback_message:
            user_messages_draft.append((BASIC_FEEDBACK_MESSAGE(None), prev_critique, WM[-1][1][3]))

        # Final conversation generation: only include the last observation and last critique (if there is not critique, mention the initial plan made by planner)
        ignore_observations = False
        ignore_critiques = False

        for feedback_message, critique, page in user_messages_draft[::-1]:
            if ignore_observations:
                page_change = None
                m = re.search(r'(\(page changed from (.+) to (.+)\))', feedback_message)
                if m is not None:
                    page_change = (m.group(2), m.group(3))

                feedback_message = BASIC_FEEDBACK_MESSAGE(page_change)

            else:
                ignore_observations = True

            if not ignore_critiques and critique is not None:
                feedback_message = feedback_message.replace('What should be the next action?', f'''
However, I got the following critique for my actions so far: 
> Criticizer: "{add_period(critique)}" 
Considering the critique, what should be the next action?'''.strip())
                
                ignore_critiques = True

            user_messages.insert(0, feedback_message)

        initial_plan = f'{add_period(self.task.plan)} ' if not has_critique else ''

        first_user_message = f'''
My name is {agent_config.persona_name} and I am using an application named {agent_config.app_name} to accomplish the following task: 
* Task: {self.task} ({remove_period(self.task.end_condition)})

I'm currently on the {self.task.start_state.activity} page. {initial_plan}What should be the first action?
        '''.strip()

        user_messages.insert(0, first_user_message)

        return user_messages, assistant_messages

    
