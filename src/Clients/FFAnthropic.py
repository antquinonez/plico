# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.
# 
# WARNING: This code contains sensitive technology requiring explicit authorization
# for possession or use. Unauthorized possession is strictly prohibited and will
# result in legal action. Licensed use requires signed agreement and compliance
# with all security requirements.
# 
# Contact: antquinonez@farfiner.com
# filename: src/lib/AI/FFAnthropic.py

import os
import time
import logging
from typing import Optional, List
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

class FFAnthropic:
    def __init__(self, config: Optional[dict] = None, **kwargs):
        logger.info("Initializing FFAnthropic")

        # DEFAULT VALUES
        default_max_model = 'max-tokens-3-5-sonnet-2024-07-15'
        defaults = {
            'model': "claude-3-5-sonnet-20240620",
            'max_tokens': 2000,
            'max_model_max_tokens': 8192,
            'temperature': 0.5,
            'instructions': "Respond accurately to user queries. Never start with a preamble, such as 'The provided JSON data structure has been reordered and formatted as valid'. Immediately address the ask or request. Do not add meta information about your response. If there's nothing to do, answer with ''"
        }

        # Combine config and kwargs, with kwargs taking precedence
        all_config = {**(config or {}), **kwargs}

        for key, value in all_config.items():
            match key:
                case 'api_key':
                    self.api_key = value or os.getenv('ANTHROPIC_TOKEN')
                case 'model':
                    self.model = value
                case 'temperature':
                    self.temperature = float(value)
                case 'max_model' | 'use_max_model':
                    if value:
                        self.max_model = all_config.get('max_model', default_max_model) or os.getenv('ANTHROPIC_MAX_MODEL', default_max_model)
                        self.max_tokens = int(all_config.get('max_model_max_tokens'))
                case 'max_tokens':
                    if not hasattr(self, 'max_tokens'):
                        self.max_tokens = int(value)
                case 'system_instructions':
                    self.system_instructions = value

        # Set default values if not set
        self.api_key = getattr(self, 'api_key', os.getenv('ANTHROPIC_TOKEN'))
        self.model = getattr(self, 'model', os.getenv('ANTHROPIC_MODEL', defaults['model']))
        self.temperature = getattr(self, 'temperature', float(os.getenv('ANTHROPIC_TEMPERATURE', defaults['temperature'])))
        self.max_tokens = getattr(self, 'max_tokens', int(os.getenv('ANTHROPIC_MAX_TOKENS', defaults['max_tokens'])))
        self.system_instructions = getattr(self, 'system_instructions', os.getenv('ANTHROPIC_ASSISTANT_INSTRUCTIONS', defaults['instructions']))
        self.max_model = getattr(self, 'max_model', None)

        logger.debug(f"Model: {self.model}, Temperature: {self.temperature}, Max Tokens: {self.max_tokens}")
        logger.debug(f"System instructions: {self.system_instructions}")
        logger.debug(f"Max model: {self.max_model}")

        self.conversation_history = []
        self.client: Anthropic = self._initialize_client()
             
    def _initialize_client(self) -> Anthropic:
        logger.info("Initializing Anthropic client")
        api_key = self.api_key
        if not api_key:
            logger.error("API key not found")
            raise ValueError("API key not found")
        
        return Anthropic(api_key=api_key)

    def generate_response(self, prompt: str) -> str:
        logger.debug(f"Generating response for prompt: {prompt}")

        try:
            self.conversation_history.append({"role": "user", "content": prompt})
            
            if self.max_model:
                logger.info(f"Using max model: {self.max_model}")
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=self.system_instructions,
                    messages=self.conversation_history,
                    extra_headers={"anthropic-beta": self.max_model}
                )
            else:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=self.system_instructions,
                    messages=self.conversation_history
                )                
            
            assistant_response = response.content[0].text
            self.conversation_history.append({"role": "assistant", "content": assistant_response})
            
            logger.info("Response generated successfully")
            return assistant_response
        except Exception as e:
            logger.error("Problem with response generation")
            logger.error(f"  -- exception: {str(e)}")
            logger.error(f"  -- model: {self.model}")
            logger.error(f"  -- system: {self.system_instructions}")
            logger.error(f"  -- conversation history: {self.conversation_history}")
            logger.error(f"  -- max_model: {self.max_model}")
            logger.error(f"  -- max_tokens: {self.max_tokens}")
            logger.error(f"  -- temperature: {self.temperature}")
            
            raise RuntimeError(f"Error generating response from Claude: {str(e)}")

    def clear_conversation(self):
        logger.info("Clearing conversation history")
        self.conversation_history = []