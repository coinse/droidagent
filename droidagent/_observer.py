import os
import time
import random
import logging

from .config import agent_config
from .app_state import AppState

from .types.action import Action
from .utils.logger import Logger

from .prompts.summarize_state import summarize_state_change

logger = Logger(__name__)

class Observer:
    def __init__(self, memory, prompt_recorder=None):
        self.memory = memory
        self.prompt_recorder = prompt_recorder

    def observe_action_result(self):
        previous_action = self.memory.working_memory.previous_action
        if previous_action is None or not isinstance(previous_action, Action):
            return None # only observe after an agent-decided action is taken

        observation = summarize_state_change(self.memory, self.prompt_recorder)

        if AppState.previous_activity != AppState.current_activity:
            if observation is None:
                observation = f'The page changed from {AppState.previous_activity} to {AppState.current_activity}'
            observation += f' (page changed from {AppState.previous_activity} to {AppState.current_activity})'

        if observation is None:
            if previous_action.target_widget is not None and previous_action.target_widget.signature is not None:
                self.memory.widget_knowledge.add_widget_wise_observation(
                    AppState.previous_activity, 
                    AppState.previous_gui_state.signature,
                    previous_action.target_widget.signature, 
                    None,
                    previous_action, 
                    self.memory.working_memory.task
                )
            return None

        self.memory.working_memory.add_step(observation, AppState.current_activity, 'OBSERVATION')
        
        if previous_action.target_widget is not None and previous_action.target_widget.signature is not None:
            self.memory.widget_knowledge.add_widget_wise_observation(
                AppState.previous_activity, 
                AppState.previous_gui_state.signature, 
                previous_action.target_widget.signature, 
                observation,
                previous_action, 
                self.memory.working_memory.task
            )

        return observation

    def detect_state_change(self, old_state, new_state):
        # Fine-grained observation of the state change, avoiding hallucination
        changed_widgets = []
        new_widgets = []
        disappeared_widgets = []

        old_widgets = {}

        for w in old_state.widgets:
            if w.widget_description is None:
                continue
            key = w.signature
            old_widgets[key] = w

        existing_widgets = []
        for w in new_state.widgets:
            if w.widget_description is None:
                continue
            key = w.signature
            existing_widgets.append(key)

            if key not in old_widgets:
                new_widgets.append((f'New widget appeared: {w.stringify()}', key, new_state.activity))
            else:
                old_w = old_widgets[key]
                if old_w.state_properties != w.state_properties:
                    changed_widgets.append((f'The state of {old_w.stringify(include_modifiable_properties=False)} changed from {old_w.state_properties} to {w.state_properties}', key, new_state.activity))
                elif old_w.widget_description.get('text', None) != w.widget_description.get('text', None):
                    old_text = old_w.widget_description.get('text', "[empty]")
                    new_text = w.widget_description.get('text', "[empty]")
                    if old_text == "[empty]":
                        changed_widgets.append((f'The text "{new_text}" inputted in {old_w.stringify(include_modifiable_properties=False)}', key, new_state.activity))
                    elif new_text == "[empty]":
                        changed_widgets.append((f'The text of {old_w.stringify(include_modifiable_properties=False)} was "{old_text}", but now it is empty', key, new_state.activity))
                    else:
                        changed_widgets.append((f'The text of {old_w.stringify(include_modifiable_properties=False)} changed from "{old_text}" to "{new_text}"'), key, new_state.activity)

        for w in old_widgets:
            if w not in existing_widgets:
                disappeared_widgets.append((f'The widget disappeared: {old_widgets[w].stringify()}', key, old_state.activity))

        return new_widgets + changed_widgets + disappeared_widgets
