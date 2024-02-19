import os
import json
import time
import random
import requests

import logging
import friendlywords as fw

from datetime import datetime
from pathlib import Path

from .app_state import AppState
from .types.gui_state import GUIState
from .memories.memory import Memory
from .utils.prompt_recorder import PromptRecorder
from .utils.logger import Logger
from .model import APIUsageManager

from .config import agent_config

from ._observer import Observer
from ._planner import Planner
from ._actor import Actor
from ._reflector import Reflector

from ._actor_gptdroid import GPTDroidActor
from ._actor_nocritique_noknowledge import NoCritiqueActor
from ._actor_noknowledge import NoKnowledgeActor
from ._planner_noknowledge import NoKnowledgePlanner


os.environ['TOKENIZERS_PARALLELISM'] = 'false'

MODE_PLAN = 'plan'
MODE_ACT = 'act'
MODE_REFLECT = 'reflect'
MODE_OBSERVE = 'observe'

MAX_ACTIONS = 13

logger = Logger(__name__)
    
class Agent:
    def __init__(self, output_dir, app=None):
        if app is None:
            raise NotImplementedError # TODO: load agent snapshot from output_dir
        
        else:
            agent_config.set_app(app)
            agent_config.set_output_dir(output_dir)
            agent_config.save()

            exp_id = fw.generate('po', separator='-')

            self.exp_id = exp_id
            self.prompt_recorder = PromptRecorder()
            self.memory = Memory(name=self.exp_id)

        AppState.initialize(agent_config.app_name, agent_config.app_activities)
        logger.info(f'Initialized an Agent with ID: {exp_id}')

    def save_memory_snapshot(self):
        memory_snapshot_dir = os.path.join(agent_config.agent_output_dir, 'memory_snapshots', f'step_{self.step_count}')
        os.makedirs(memory_snapshot_dir, exist_ok=True)
        self.memory.save_snapshot(memory_snapshot_dir)

    def step(self, droidbot_state=None):
        raise NotImplementedError

    def set_current_gui_state(self, droidbot_state):
        AppState.set_current_gui_state(droidbot_state)
        self.prompt_recorder.set_state_tag(AppState.current_gui_state.tag)

    @property
    def exp_data(self):
        return {
            'app_activities': AppState.activities,
            'visited_activities': AppState.visited_activities,
            'task_results': self.memory.task_memory.task_results,
            'API_usage': APIUsageManager.usage,
            'API_response_time': APIUsageManager.response_time
        }


class TaskBasedAgent(Agent):
    """
    Task-based Agent
    """
    def __init__(self, output_dir, app=None, persona=None, debug_mode=False):
        super().__init__(output_dir, app=app)

        if app is None:
            raise NotImplementedError # TODO: load agent snapshot from output_dir
        else:
            self.initialize(app, persona, debug_mode=debug_mode)

        logger.info(f'Target App: {agent_config.app_name} ({agent_config.package_name})')
        logger.info(f'Ultimate Goal: {agent_config.ultimate_goal}')

    def initialize(self, app, persona, debug_mode=False):
        for initial_knowledge in persona['initial_knowledge']:
            self.inject_knowledge_entry(initial_knowledge, 'INITIAL_KNOWLEDGE')
        
        if debug_mode:
            agent_config.set_debug_mode()
            
        agent_config.set_persona(persona)
        agent_config.save()

        self.observer = Observer(self.memory, self.prompt_recorder)
        self.planner = Planner(self.memory, self.prompt_recorder)
        self.actor = Actor(self.memory, self.prompt_recorder)
        self.reflector = Reflector(self.memory, self.prompt_recorder)
        self.mode = MODE_PLAN
        self.step_count = 0

    @property
    def task(self):
        return self.memory.working_memory.task

    @property
    def persona_name(self):
        return agent_config.persona_name

    def step(self, droidbot_state=None):
        self.step_count += 1
        logger.info(f'Step {self.step_count}, Mode: {self.mode}')
        logger.info(f'Current Activity Coverage: {len(AppState.visited_activities)} / {len(agent_config.app_activities)}')

        if droidbot_state is not None:
            self.set_current_gui_state(droidbot_state)

        with open(os.path.join(agent_config.agent_output_dir, 'exp_data.json'), 'w') as f:
            json.dump(self.exp_data, f, indent=2)

        if self.mode == MODE_PLAN:
            """
            * Plan
            """
            self.actor.reset()
            first_action = self.planner.plan_task()

            if first_action is not None:
                self.mode = MODE_OBSERVE
                self.actor.action_count += 1
                self.actor.critique_countdown -= 1
                logger.info(f'* New task: {self.task}')
                logger.info(f'* First action: {first_action}')

                return first_action

            return None
        
        elif self.mode == MODE_REFLECT:
            """
            * Reflect
            """
            task_result = self.reflector.reflect()

            logger.info(f'* Task Reflection: {task_result}')

            self.mode = MODE_PLAN

            return None

        elif self.mode == MODE_ACT:
            """
            * Action
            """
            logger.info(f'[Current Task] {self.task}')

            if self.actor.action_count >= MAX_ACTIONS:
                # If task does not end after MAX_ACTIONS actions, reflect
                self.mode = MODE_REFLECT
                self.inject_action_entry('The task gets too long, so I am going to put off the task and start a new task that could be easily achievable instead.', 'TASK_ABORTED')
                logger.info(f'Task not completed with max actions, aborting...')
                return None

            next_action = self.actor.act()

            if next_action is None:
                self.mode = MODE_REFLECT
                return None
            else:
                logger.info(f'* Next action: {next_action}')
                self.mode = MODE_OBSERVE
                return next_action

        elif self.mode == MODE_OBSERVE:
            """
            * Observe
            """
            action_result = self.observer.observe_action_result()
            if action_result is not None:
                logger.info(f'* Observation: """\n{action_result}\n"""')
            else:
                logger.info(f'* Observation: No detectable change.')

            self.mode = MODE_ACT
            return None

    def inject_knowledge_entry(self, description, entry_type):
        self.memory.inject_entry(description, entry_type)

    def inject_action_entry(self, description, entry_type):
        self.memory.working_memory.add_step(description, AppState.current_activity, entry_type)

# Ablation 1: Actor-only, GPTDroid replication
class ActorOnlyAgent(Agent):
    def __init__(self, output_dir, app=None):
        super().__init__(output_dir, app=app)

        self.actor = GPTDroidActor(self.memory)
        self.step_count = 0

        assert app is not None

    @property
    def persona_name(self):
        return agent_config.persona_name

    def step(self, droidbot_state=None):
        self.step_count += 1
        logger.info(f'Step {self.step_count}')
        logger.info(f'Current Activity Coverage: {len(AppState.visited_activities)} / {len(agent_config.app_activities)}')

        if droidbot_state is not None:
            self.set_current_gui_state(droidbot_state)

        action = None
        if self.step_count == 1:
            action = self.actor.decide_first_action()
        else:
            action = self.actor.decide_next_action()

        logger.info(f'* Next action: {action}')

        PromptRecorder.record_gptdroid_conversation(self.actor.current_prompt, self.actor.full_prompt)
    
        return action

# Ablation 2: Task-based, w/o critique, w/o knowledge
class TaskBasedAgentNoCritiqueNoKnowledge(Agent):
    """
    Task-based Agent
    """
    def __init__(self, output_dir, app=None, persona=None, debug_mode=False):
        super().__init__(output_dir, app=app)

        if app is None:
            raise NotImplementedError # TODO: load agent snapshot from output_dir
        else:
            self.initialize(app, persona, debug_mode=debug_mode)

        logger.info(f'Target App: {agent_config.app_name} ({agent_config.package_name})')
        logger.info(f'Ultimate Goal: {agent_config.ultimate_goal}')

    def initialize(self, app, persona, debug_mode=False):
        for initial_knowledge in persona['initial_knowledge']:
            self.inject_knowledge_entry(initial_knowledge, 'INITIAL_KNOWLEDGE')
            # FIXME: add to knowledge memory?
        
        if debug_mode:
            agent_config.set_debug_mode()
            
        agent_config.set_persona(persona)
        agent_config.save()

        self.observer = Observer(self.memory, self.prompt_recorder)
        self.planner = NoKnowledgePlanner(self.memory, self.prompt_recorder)
        self.actor = NoCritiqueActor(self.memory, self.prompt_recorder)
        self.reflector = Reflector(self.memory, self.prompt_recorder)
        self.mode = MODE_PLAN
        self.step_count = 0

    @property
    def task(self):
        return self.memory.task

    @property
    def persona_name(self):
        return agent_config.persona_name

    def step(self, droidbot_state=None):
        self.step_count += 1
        logger.info(f'Step {self.step_count}, Mode: {self.mode}')
        logger.info(f'Current Activity Coverage: {len(AppState.visited_activities)} / {len(agent_config.app_activities)}')

        with open(os.path.join(agent_config.agent_output_dir, 'exp_data.json'), 'w') as f:
            json.dump(self.exp_data, f, indent=2)

        if droidbot_state is not None:
            self.set_current_gui_state(droidbot_state)

        if self.mode == MODE_PLAN:
            """
            * Plan
            """
            self.actor.reset()
            first_action = self.planner.plan_task()

            if first_action is not None:
                self.mode = MODE_OBSERVE
                self.actor.action_count += 1
                logger.info(f'* New task: {self.task}')
                logger.info(f'* First action: {first_action}')

                return first_action

            return None
        
        elif self.mode == MODE_REFLECT:
            """
            * Reflect
            """
            task_result = self.reflector.reflect()

            logger.info(f'* Task Reflection: {task_result}')

            self.mode = MODE_PLAN

            return None

        elif self.mode == MODE_ACT:
            """
            * Action
            """
            logger.info(f'[Current Task] {self.task}')

            if self.actor.action_count >= MAX_ACTIONS:
                # If task does not end after MAX_ACTIONS actions, reflect
                self.mode = MODE_REFLECT
                self.inject_action_entry('The task gets too long, so I am going to put off the task and start a new task that could be easily achievable instead.', 'TASK_ABORTED')
                logger.info(f'Task not completed with max actions, aborting...')
                return None

            next_action = self.actor.act()

            if next_action is None:
                self.mode = MODE_REFLECT
                return None
            else:
                logger.info(f'* Next action: {next_action}')
                self.mode = MODE_OBSERVE
                return next_action

        elif self.mode == MODE_OBSERVE:
            """
            * Observe
            """
            action_result = self.observer.observe_action_result()
            if action_result is not None:
                logger.info(f'* Observation: """\n{action_result}\n"""')
            else:
                logger.info(f'* Observation: No detectable change.')

            self.mode = MODE_ACT
            return None


# Ablation 3: Task-based, w/o knowledge
class TaskBasedAgentNoKnowledge(Agent):
    """
    Task-based Agent
    """
    def __init__(self, output_dir, app=None, persona=None, debug_mode=False):
        super().__init__(output_dir, app=app)

        if app is None:
            raise NotImplementedError # TODO: load agent snapshot from output_dir
        else:
            self.initialize(app, persona, debug_mode=debug_mode)

        logger.info(f'Target App: {agent_config.app_name} ({agent_config.package_name})')
        logger.info(f'Ultimate Goal: {agent_config.ultimate_goal}')

    def initialize(self, app, persona, debug_mode=False):
        for initial_knowledge in persona['initial_knowledge']:
            self.inject_knowledge_entry(initial_knowledge, 'INITIAL_KNOWLEDGE')
            # FIXME: add to knowledge memory?
        
        if debug_mode:
            agent_config.set_debug_mode()
            
        agent_config.set_persona(persona)
        agent_config.save()

        self.observer = Observer(self.memory, self.prompt_recorder)
        self.planner = NoKnowledgePlanner(self.memory, self.prompt_recorder)
        self.actor = NoKnowledgeActor(self.memory, self.prompt_recorder)
        self.reflector = Reflector(self.memory, self.prompt_recorder)
        self.mode = MODE_PLAN
        self.step_count = 0

    @property
    def task(self):
        return self.memory.task

    @property
    def persona_name(self):
        return agent_config.persona_name

    def step(self, droidbot_state=None):
        self.step_count += 1
        logger.info(f'Step {self.step_count}, Mode: {self.mode}')
        logger.info(f'Current Activity Coverage: {len(AppState.visited_activities)} / {len(agent_config.app_activities)}')

        if droidbot_state is not None:
            self.set_current_gui_state(droidbot_state)

        with open(os.path.join(agent_config.agent_output_dir, 'exp_data.json'), 'w') as f:
            json.dump(self.exp_data, f, indent=2)

        if self.mode == MODE_PLAN:
            """
            * Plan
            """
            self.actor.reset()
            first_action = self.planner.plan_task()

            if first_action is not None:
                self.mode = MODE_OBSERVE
                self.actor.action_count += 1
                self.actor.critique_countdown -= 1
                logger.info(f'* New task: {self.task}')
                logger.info(f'* First action: {first_action}')

                return first_action

            return None
        
        elif self.mode == MODE_REFLECT:
            """
            * Reflect
            """
            task_result = self.reflector.reflect()

            logger.info(f'* Task Reflection: {task_result}')

            self.mode = MODE_PLAN

            return None

        elif self.mode == MODE_ACT:
            """
            * Action
            """
            logger.info(f'[Current Task] {self.task}')

            if self.actor.action_count >= MAX_ACTIONS:
                # If task does not end after MAX_ACTIONS actions, reflect
                self.mode = MODE_REFLECT
                self.inject_action_entry('The task gets too long, so I am going to put off the task and start a new task that could be easily achievable instead.', 'TASK_ABORTED')
                logger.info(f'Task not completed with max actions, aborting...')
                return None

            next_action = self.actor.act()

            if next_action is None:
                self.mode = MODE_REFLECT
                return None
            else:
                logger.info(f'* Next action: {next_action}')
                self.mode = MODE_OBSERVE
                return next_action

        elif self.mode == MODE_OBSERVE:
            """
            * Observe
            """
            action_result = self.observer.observe_action_result()
            if action_result is not None:
                logger.info(f'* Observation: """\n{action_result}\n"""')
            else:
                logger.info(f'* Observation: No detectable change.')

            self.mode = MODE_ACT
            return None