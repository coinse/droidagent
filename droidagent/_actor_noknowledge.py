import os
import random
import logging
import time

from .app_state import AppState
from .utils.stringutil import add_period
from .utils.logger import Logger
from .types.action import *

from .prompts.act_noknowledge import prompt_action
from .prompts.critique_noknowledge import prompt_critique


MAX_RETRY = 5
CRITIQUE_COUNTDOWN = 4

logger = Logger(__name__)

class NoKnowledgeActor:
    def __init__(self, memory, prompt_recorder=None):
        self.critique_countdown = CRITIQUE_COUNTDOWN
        self.memory = memory
        self.prompt_recorder = prompt_recorder
        self.action_count = 0

    def reset(self):
        self.action_count = 0
        self.critique_countdown = CRITIQUE_COUNTDOWN
    
    def act(self): # use function call for selecting the action
        assert self.memory.working_memory.task is not None, 'No task is registered'

        # Inject critique periodically
        if self.critique_countdown == 0:
            self.critique_countdown = CRITIQUE_COUNTDOWN
            critique, workaround = prompt_critique(self.memory, self.prompt_recorder)
            full_critique = ''
            if critique is not None:
                full_critique += f'{add_period(critique)}'
                logger.info(f'* Critique during a task: {critique}')
                if workaround is not None:
                    full_critique += f' {add_period(workaround)}'
                    logger.info(f'* Suggested workaround: {workaround}')
            
            full_critique = full_critique.strip()
            if len(full_critique) > 0:
                self.memory.working_memory.add_step(full_critique, AppState.current_activity, 'CRITIQUE')

        self.critique_countdown -= 1

        action = prompt_action(self.memory, self.prompt_recorder)

        if action is not None:
            self.action_count += 1
            self.memory.working_memory.add_step(action, AppState.current_activity, 'ACTION')

        return action
