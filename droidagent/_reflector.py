import os
import logging

from .config import agent_config
from .model import APIUsageManager
from .types.action import *
from .utils.logger import Logger
from .prompts.reflect_task import reflect_task


logger = Logger(__name__)


class Reflector:
    def __init__(self, memory, prompt_recorder=None):
        self.memory = memory
        self.prompt_recorder = prompt_recorder

    def reflect(self):
        task = self.memory.working_memory.task

        task_result_summary, task_result, reflections = reflect_task(self.memory, self.prompt_recorder)
        
        task.add_result(task_result, task_result_summary)
        self.memory.task_memory.record_task_result(task, reflections, self.memory.working_memory.steps)

        return task_result_summary
