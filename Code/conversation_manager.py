import time

class ConversationManager:
    def __init__(self):
        self.states = {}

    def get_state(self, user_id):
        if user_id not in self.states:
            self.reset_state(user_id)
        return self.states[user_id]

    def reset_state(self, user_id):
        self.states[user_id] = {
            "step": "init",
            "original_input": None,
            "expanded_query": None,
            "history": [],
            "last_updated": time.time()
        }

    def update_state(self, user_id, **kwargs):
        state = self.get_state(user_id)
        state.update(kwargs)
        state["last_updated"] = time.time()

    def add_history(self, user_id, role, content):
        state = self.get_state(user_id)
        state["history"].append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })

