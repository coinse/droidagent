from collections import defaultdict

class Task:
    def __init__(self, summary, description, plan='', end_condition=''):
        self.summary = summary
        self.assessment = None
        self.result_summary = None
        self.description = description
        self.explored_activities = defaultdict(int)
        self.explored_states = []

        self.plan = plan # concrete plan to execute the task
        self.end_condition = end_condition

        self.entry_id = None

    def add_result(self, assessment, result_summary):
        self.assessment = assessment
        self.result_summary = result_summary

    def register_plan(self, plan):
        self.plan = plan

    def add_explored_activity(self, activity):
        self.explored_activities[activity] += 1

    def add_explored_state(self, state):
        self.explored_states.append(state)

    @property
    def start_state(self):
        if len(self.explored_states) == 0:
            return None
        return self.explored_states[0]

    def __str__(self):
        return f'{self.summary}'
