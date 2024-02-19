from datetime import datetime
import os

from ..config import agent_config
from ..model import stringify_prompt, zip_messages

class PromptRecorder:
    state_tag = 'initial'

    @classmethod
    def set_state_tag(cls, state_tag):
        cls.state_tag = state_tag
    
    @classmethod
    def record(cls, prompt, mode):
        prompt_str = stringify_prompt(prompt)
        with open(os.path.join(agent_config.agent_output_dir, 'prompts', f'prompt_{cls.state_tag}_{datetime.now().strftime("%H%M%S")}_{mode}.txt'), 'w') as f:
            f.write(prompt_str)

    @classmethod
    def record_gptdroid_conversation(cls, current_prompt, full_prompt):
        full_prompt = {
            'system_message': current_prompt['system_message'],
            'user_messages': full_prompt['user_messages'] + current_prompt['user_messages'],
            'assistant_messages': full_prompt['assistant_messages'] + current_prompt['assistant_messages'],
        }
        with open(os.path.join(agent_config.agent_output_dir, 'conversation.json'), 'w') as f:
            json.dump(full_prompt, f, indent=2)

        with open(os.path.join(agent_config.agent_output_dir, 'conversation.txt'), 'w') as f:
            f.write(stringify_prompt(zip_messages(full_prompt['system_message'], full_prompt['user_messages'], full_prompt['assistant_messages'])))
