from ..config import agent_config
from ..utils.activity_name_manager import ActivityNameManager
from ..utils.stringutil import remove_quotes
from ..utils.viewtreeutil import minimize_view_tree
from ..utils.logger import Logger

from .action import initialize_possible_actions, initialize_screen_scroll_action, initialize_go_back_action, initialize_enter_key_action
from .widget import Widget

from abc import ABC, abstractmethod
from collections import defaultdict, OrderedDict
from functools import cached_property

import json
import copy
import difflib
import logging

CONTEXT_LENGTH_LIMIT = 15000

logger = Logger(__name__)


class GUIStateBase(ABC):
    @abstractmethod
    def from_droidbot_state(self, droidbot_state):
        pass

    @abstractmethod
    def get_widget_by_id(self, view_id):
        pass

    @abstractmethod
    def get_widget_by_signature(self, signature):
        pass

    @abstractmethod
    def describe_screen(self, memory=None, prompt_recorder=None):
        pass

    @abstractmethod
    def diff(self, other):
        pass

    @abstractmethod
    def signature(self):
        pass

    @abstractmethod
    def actiontype2widgets(self):
        pass

    @abstractmethod
    def interactable_widget_ids(self):
        pass


class GUIState(GUIStateBase):
    def __init__(self):
        self.tag = None
        self.activity = None
        self.droidbot_state = None
        self.activity_stack = []
        self.possible_actions = []
        self.lost_messages = set()

    def from_droidbot_state(self, droidbot_state):
        """
        Convert the view tree and view list from DroidBot to a GUI state
        :param _view_tree: dict, the view tree from DroidBot
        """
        self.droidbot_state = droidbot_state
        self.activity = ActivityNameManager.fix_activity_name(droidbot_state.foreground_activity)
        self.activity_stack = droidbot_state.activity_stack
        self.tag = droidbot_state.tag
        view_tree = minimize_view_tree(droidbot_state.view_tree)

        self.root_widgets = []
        self.widgets = []
        for root_elem in view_tree:
            self.root_widgets.append(traverse_widgets(root_elem, self.widgets, droidbot_state.views))

        return self
    
    def get_app_activity_depth(self):
        package_name = agent_config.package_name
        depth = 0
        for activity_str in self.activity_stack:
            if package_name in activity_str:
                return depth
            depth += 1
        
        return -1

    def get_widget_by_id(self, view_id):
        """
        Get the widget with the given view ID
        :param view_id: int, the view ID
        :return: Widget, the widget with the given view ID
        """
        for widget in self.widgets:
            if widget.view_id == view_id:
                return widget
        
        return None

    def get_widget_by_signature(self, signature):
        """
        Get the widget with the given signature
        :param signature: str, the signature
        :return: Widget, the widget with the given signature
        """
        for widget in self.widgets:
            if widget.signature == signature:
                return widget
        
        return None

    def __str__(self):
        return self.describe_screen()

    def describe_screen_w_memory(self, memory, length_limit=CONTEXT_LENGTH_LIMIT, show_id=True, prompt_recorder=None, include_widget_knowledge=True):
        """
        From a given GUI state, creates a description of the GUI state including the list of interactable widgets and non-interactable widgets
        """
        def inject_widget_knowledge(widget, show_id):
            widget_info = widget.to_dict(include_id=show_id)

            if ('Main' in self.activity or self.activity == agent_config.main_activity) and 'content_description' in widget_info:
                # If "Navigate up" widget is in the main page, change its name to "Menu"
                if widget_info['content_description'].lower() == 'navigate up':
                    widget_info['content_description'] = 'Menu'

            # merge textview children
            text_only_children = [child for child in widget.children if child.widget_type == 'TextView' and len(child.children) == 0 and len(child.possible_action_types) == 0 and child.text is not None]

            children_merged = len(text_only_children) > 0 and len(text_only_children) == len(widget.children) and widget.text is None

            if children_merged:
                # all children are textviews and it does not have text property, substitute its text property with the text of its children, and remove the children to the final representation.
                widget_info['text'] = [child.text for child in text_only_children if child.text is not None]
                if len(widget_info['text']) == 0:
                    del widget_info['text']

            if len(widget.possible_action_types) > 0:
                performed_action_types = memory.widget_knowledge.get_performed_action_counts(self.activity, widget.signature)
                interaction_count = 0
                for action_type in performed_action_types:
                    interaction_count += performed_action_types[action_type]

                widget_info['num_prev_actions'] = interaction_count

                if include_widget_knowledge and memory.widget_knowledge.has_widget_knowledge(self.activity, widget.signature):
                    widget_knowledge = memory.widget_knowledge.retrieve_widget_knowledge(
                        self,
                        widget, 
                        prompt_recorder=prompt_recorder
                    )
                    if widget_knowledge is not None:
                        widget_info['widget_role_inference'] = widget_knowledge

            children_w_knowledge = []

            if not children_merged:
                for child in widget.children:
                    children_w_knowledge.append(inject_widget_knowledge(child, show_id))

            if 'children' in widget_info:
                del widget_info['children']
            if len(children_w_knowledge) > 0:
                widget_info['children'] = children_w_knowledge
            return widget_info

        view_hierarchy = {
            'page_name': self.activity,
            'children': []
        }
        for widget in self.root_widgets:
            view_hierarchy['children'].append(inject_widget_knowledge(widget, show_id))

        screen_description = json.dumps(view_hierarchy, indent=2, ensure_ascii=False)

        if length_limit and len(screen_description) > length_limit:
            screen_description = screen_description[:length_limit] + '[...truncated...]'
            logger.warning(f'Screen description is too long ({len(screen_description)} > {length_limit}). Truncated. (state tag: {self.tag}))')
        
        screen_description = remove_quotes(screen_description) # remove all quotes to reduce the number of tokens
        return screen_description
    
    def describe_screen(self, length_limit=CONTEXT_LENGTH_LIMIT, show_id=True):
        view_hierarchy = {
            'page_name': self.activity,
            'children': []
        }

        for widget in self.root_widgets:
            view_hierarchy['children'].append(widget.to_dict(include_id=show_id))

        screen_description = json.dumps(view_hierarchy, indent=2, ensure_ascii=False)

        if length_limit and len(screen_description) > length_limit:
            screen_description = screen_description[:length_limit] + '[...truncated...]'
            logger.warning(f'Screen description is too long ({len(screen_description)} > {length_limit}). Truncated. (state tag: {self.tag}))')

        screen_description = remove_quotes(screen_description) # remove all double quotes to reduce the number of tokens
        return screen_description

    def describe_widgets(self, length_limit=CONTEXT_LENGTH_LIMIT, show_id=True):
        desc = ''

        for widget in self.widgets:
            desc += widget.dump(indent=None) + '\n'
        
        desc = desc.strip()

        if length_limit and len(desc) > length_limit:
            desc = desc[:length_limit] + '[...truncated...]'
            logger.warning(f'Screen description is too long ({len(screen_description)} > {length_limit}). Truncated. (state tag: {self.tag}))')
        
        return desc

    def describe_widgets_NL(self, length_limit=CONTEXT_LENGTH_LIMIT):
        desc = ''

        for widget in self.widgets:
            desc += widget.stringify(include_children_text=False) + '\n'
        
        desc = desc.strip()

        if length_limit and len(desc) > length_limit:
            desc = desc[:length_limit] + '[...truncated...]'
            logger.warning(f'Screen description is too long ({len(desc)} > {length_limit}). Truncated. (state tag: {self.tag}))')
        
        return desc

    def diff(self, other):
        """
        Calculate the difference between two GUI states
        """
        diff = difflib.ndiff(self.describe_widgets().splitlines(keepends=True), other.describe_widgets().splitlines(keepends=True))
        return ''.join(diff)

    def diff_widgets(self, other):
        changed_widgets = []
        appeared_widgets = []
        disappeared_widgets = []

        old_widgets = {}
        new_widgets = {}

        for w in self.widgets:
            if w.signature is None:
                continue
            key = w.signature
            old_widgets[key] = w

        for w in other.widgets:
            if w.signature is None:
                continue
            key = w.signature
            new_widgets[key] = w

            if key not in old_widgets:
                appeared_widgets.append(w)
            else:
                old_w = old_widgets[key]
                if old_w.elem_dict.get('state', []) != w.elem_dict.get('state', []):
                    changed_widgets.append((w, {
                        'old_state': old_w.elem_dict.get('state', []),
                        'new_state': w.elem_dict.get('state', [])
                    }))
                elif old_w.elem_dict.get('text', '') != w.elem_dict.get('text', ''):
                    old_text = old_w.elem_dict.get('text', '')
                    new_text = w.elem_dict.get('text', '')
                    changed_widgets.append((w, {
                        'old_text': old_text,
                        'new_text': new_text
                    }))
                    
        for key in old_widgets:
            if key not in new_widgets:
                disappeared_widgets.append(old_widgets[key])

        return changed_widgets, appeared_widgets, disappeared_widgets

    @cached_property
    def signature(self):
        """
        natural language representation of the GUI state (used as a query for associative memory)
        """
        gui_state = f'{self.activity} page: '
        for widget in self.widgets:
            gui_state += f'{widget.stringify()}, '
        return gui_state[:-2]

    @cached_property
    def actiontype2widgets(self):
        actiontype2widgets = defaultdict(dict)
        for w in self.widgets:
            for action_type in w.possible_action_types:
                assert w.view_id is not None, 'interactable widgets must have view ID'
                actiontype2widgets[action_type][w.view_id] = w
        
        return actiontype2widgets

    @cached_property
    def interactable_widget_ids(self):
        interactable_widget_ids = set()
        for w in self.widgets:
            if len(w.possible_action_types) > 0:
                interactable_widget_ids.add(w.view_id)
        return interactable_widget_ids


def traverse_widgets(elem, processed_widgets, original_views):
    """
    Traverse all child widgets so that all required properties are included
    """
    new_elem = OrderedDict()
    possible_action_types = []
    state_properties = []

    if elem.get('clickable', False) or elem.get('checkable', False):
        possible_action_types.append('touch')
    if elem.get('long_clickable', False):
        possible_action_types.append('long_touch')
    if elem.get('editable', False):
        possible_action_types.append('set_text')
    if elem.get('scrollable', False):
        possible_action_types.append('scroll')

    if elem.get('focused', False):
        state_properties.append('focused')
    if elem.get('checked', False):
        state_properties.append('checked')
    if elem.get('selected', False):
        state_properties.append('selected')

    if 'temp_id' in elem and len(possible_action_types) > 0:
        elem_ID = elem['temp_id']
        new_elem['ID'] = elem_ID
        new_elem['view_str'] = original_views[elem_ID]['view_str']
    if 'class' in elem:
        new_elem['widget_type'] = elem['class'].split('.')[-1]
        new_elem['class'] = elem['class']
    if 'text' in elem and elem['text'] is not None and len(elem['text'].strip()) > 0:
        new_elem['text'] = elem['text'] if len(elem['text']) < 100 else elem['text'][:100] + '[...]'
    if 'content_description' in elem and elem['content_description'] is not None:
        new_elem['content_description'] = elem['content_description']
    if 'resource_id' in elem and elem['resource_id'] is not None:
        new_elem['resource_id'] = elem['resource_id'].split('/')[-1]
    if 'is_password' in elem and elem['is_password']:
        new_elem['is_password'] = True
    if len(state_properties) > 0:
        new_elem['state'] = state_properties
    if len(possible_action_types) > 0:
        new_elem['possible_action_types'] = possible_action_types

    if 'view_str' in elem:
        new_elem['view_str'] = elem['view_str']

    new_elem['bounds'] = elem['bounds']

    children_widgets = []
    for child in elem.get('children', []):
        children_widgets.append(traverse_widgets(child, processed_widgets, original_views))
    
    new_elem['children'] = children_widgets

    widget = Widget().from_dict(new_elem)
    
    processed_widgets.append(widget)

    return widget