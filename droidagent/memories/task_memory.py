from ..types.action import Action

class TaskMemory:
    def __init__(self, primary_storage, knowledge_storage):
        self.storage = primary_storage
        self.knowledge_storage = knowledge_storage
        self.task_results = {} # To store experiment results

    def record_task(self, task, description):
        entry_id = self.storage.add_entry(
            document=description,
            metadata={
                'type': 'TASK',
                'task': task.summary
            }
        )

        return entry_id

    def record_task_result(self, task, reflections, working_memory_steps):
        assert task.assessment is not None, f'No task assessment found for the task "{task.summary}"'

        # Logging to collect experiment results
        working_memory_record = []
        for desc, record_type, timestamp, page in working_memory_steps:
            action_data = None
            events = []
            if isinstance(desc, Action):
                action_data = desc.get_reproducible_record()
            if record_type == 'ACTION':
                events = desc.events
            working_memory_record.append({
                'description': str(desc),
                'type': record_type,
                'timestamp': timestamp,
                'page': page,
                'action_data': action_data,
                'events': events
            })
        
        self.task_results[task.summary] = {
            'result': task.assessment,
            'summary': task.result_summary,
            'reflections': reflections,
            'num_actions': len([record for record in working_memory_record if record['type'] == 'ACTION']),
            'num_critiques': len([record for record in working_memory_record if record['type'] == 'CRITIQUE']),
            'visited_pages_during_task': task.explored_activities,
            'task_execution_history': working_memory_record
        }

        # Add task result to permanent storages
        self._add_task_result_to_storage(task)
        for reflection in reflections:
            self._add_task_reflection_to_storage(task, reflection)

    def _add_task_result_to_storage(self, task):
        saved_task_entry = self.storage.get(ids=[str(task.entry_id)])
        assert saved_task_entry is not None and len(saved_task_entry['metadatas']) > 0 , f'No task entry found for {task.entry_id} (task: {task.summary})'

        # Update task metadata
        saved_task_entry['metadatas'][0]['task_result'] = task.assessment
        self.storage.upsert(**saved_task_entry)

        # Add a task result summary 
        result_entry_id = self.storage.add_entry(
            document=task.result_summary.strip(),
            metadata={
                'type': 'TASK_RESULT',
                'task': task.summary,
                'task_result': task.assessment
            },
        )

        return result_entry_id

    def _add_task_reflection_to_storage(self, task, reflection):
        self.knowledge_storage.add_entry(
            document=reflection,
            metadata={
                'type': 'TASK',
                'reflection': reflection,
                'task': task.summary
            }
        )

    def retrieve_task_history(self, max_len=20):
        entries = self.storage.get(where={'$or': [
            {'type': 'TASK_RESULT'},
            {'type': 'INITIAL_KNOWLEDGE'}
        ]})

        return self.storage.stringify_entries(entries, mode='task_history', max_len=max_len)
        
    def retrieve_task_reflections(self, state, N=5):
        query = state.signature

        relevant_entries = self.knowledge_storage.query(
            query_texts=[query],
            n_results=N,
            where={'type': 'TASK'}
        )

        relevant_entries = {
            'ids': relevant_entries['ids'][0],
            'metadatas': relevant_entries['metadatas'][0],
            'documents': relevant_entries['documents'][0]
        }

        return self.knowledge_storage.stringify_entries(relevant_entries, mode='task_knowledge')