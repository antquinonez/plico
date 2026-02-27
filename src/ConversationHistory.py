# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.
#
# WARNING: This code contains sensitive technology requiring explicit authorization
# for possession or use. Unauthorized possession is strictly prohibited and will
# result in legal action. Licensed use requires signed agreement and compliance
# with all security requirements.
#
# Contact: antquinonez@farfiner.com
# filename: src/lib/AI/ConversationHistory.py


class ConversationHistory:
    def __init__(self):
        self.turns = []

    def add_turn_assistant(self, content):
        self.turns.append({"role": "assistant", "content": [{"type": "text", "text": content}]})

    def add_turn_user(self, content):
        if self.turns and self.turns[-1]["role"] == "user":
            # If the last turn was a user, update its content instead of adding a new turn
            self.turns[-1]["content"][0]["text"] += "\n" + content
        else:
            self.turns.append({"role": "user", "content": [{"type": "text", "text": content}]})

    def get_turns(self):
        result = []
        for turn in self.turns:
            if turn["role"] == "user":
                result.append(
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": turn["content"][0]["text"]}],
                    }
                )
            else:
                result.append(turn)
        return result
