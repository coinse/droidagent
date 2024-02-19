import os
import random
import logging
import time

from .app_state import AppState

from .utils import *
from .types.action import *
from .prompts.act_noknowledge import prompt_action


MAX_RETRY = 5
CRITIQUE_COUNTDOWN = 4


class NoCritiqueActor:
    def __init__(self, memory, prompt_recorder=None):
        self.memory = memory
        self.prompt_recorder = prompt_recorder
        self.action_count = 0

    def reset(self):
        self.action_count = 0
    
    def act(self): # use function call for selecting the action
        assert self.memory.working_memory.task is not None, 'No task is registered'

        action = prompt_action(self.memory, self.prompt_recorder)

        if action is not None:
            self.action_count += 1
            self.memory.working_memory.add_step(action, AppState.current_activity, 'ACTION')

        return action
