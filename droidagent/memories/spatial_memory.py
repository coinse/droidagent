from ..prompts.summarize_widget_knowledge import prompt_summarized_widget_knowledge
from collections import defaultdict

class SpatialMemory:    # Akin to human's long-term spatial memory and is stored in the permanent storage
    def __init__(self, storage):
        self.storage = storage
        self.widget_knowledge_map = {}

    def has_widget_knowledge(self, page, widget_signature):
        if page not in self.widget_knowledge_map:
            return False
        if widget_signature not in self.widget_knowledge_map[page]:
            return False

        return self.widget_knowledge_map[page][widget_signature]['observation_count'] > 0
    
    def retrieve_widget_knowledge(self, state, widget, N=5, prompt_recorder=None):
        relevant_entries = self.storage.query(
            query_texts=[state.signature],
            n_results=N,
            where={'$and': [{'type': 'WIDGET'}, {'page': state.activity}, {'widget': widget.signature}]}
        )

        relevant_entries = {
            'ids': relevant_entries['ids'][0],
            'metadatas': relevant_entries['metadatas'][0],
            'documents': relevant_entries['documents'][0]
        }

        if len(relevant_entries) == 0:
            return None

        relevant_widget_observations = self.storage.stringify_entries(relevant_entries, mode='widget_knowledge')

        widget_role_summary = prompt_summarized_widget_knowledge(widget.stringify(), relevant_widget_observations, prompt_recorder=prompt_recorder)

        self.update_widget_role_inference(state.activity, widget.signature, widget_role_summary)

        return widget_role_summary

    def get_performed_action_counts(self, page, widget_signature):
        if page not in self.widget_knowledge_map:
            return {}
        if widget_signature not in self.widget_knowledge_map[page]:
            return {}

        return self.widget_knowledge_map[page][widget_signature]['action_count']

    def add_widget_wise_observation(self, page, state_signature, widget_signature, observation, action, task):
        if page not in self.widget_knowledge_map:
            self.widget_knowledge_map[page] = {}

        if widget_signature not in self.widget_knowledge_map[page]:
            self.widget_knowledge_map[page][widget_signature] = {
                'action_count': defaultdict(lambda: 0),
                'observation_count': 0,
                'role_inference': None
            }

        action_count_map = self.widget_knowledge_map[page][widget_signature]['action_count']
        action_count_map[action.event_type] += 1

        self.widget_knowledge_map[page][widget_signature]['action_count'][action.event_type] += 1
        
        if observation is None:
            return

        self.widget_knowledge_map[page][widget_signature]['observation_count'] += 1

        self.storage.add_entry(
            document=state_signature.strip(),
            metadata={
                'type': 'WIDGET',
                'observation': observation,
                'page': page,
                'widget': widget_signature,
                'action': action.action_type_signature, 
                'task': task.summary,
            }
        )

    def update_widget_role_inference(self, page, widget_signature, inference):
        if page not in self.widget_knowledge_map:
            self.widget_knowledge_map[page] = {}
        if widget_signature not in self.widget_knowledge_map[page]:
            self.widget_knowledge_map[page][widget_signature] = {
                'action_count': defaultdict(lambda: 0),
                'role_inference': None
            }
        
        self.widget_knowledge_map[page][widget_signature]['role_inference'] = inference
    