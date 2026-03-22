import asyncio
import time
from typing import Dict, List, Union, Optional
from config import (
    SESSION_EXPIRY,
    OPENAI_MODEL,
    ANTHROPIC_MODEL,
    GEMINI_MODEL,
    GROK_MODEL,
    SYSTEM_PROMPT,
    DEFAULT_MODEL_PROVIDER,
    OPENAI_MODELS_REASONING,
)
from models.models_list import MODELS, DEFAULT_MODEL
from utils.logging_config import logger

class SessionManager:
    def __init__(self):
        self.sessions: Dict[int, Dict[str, Union[List[Dict[str, str]], float, str]]] = {}

    def get_or_create_session(self, user_id: int) -> 'Session':
        current_time = time.time()
        if user_id not in self.sessions or current_time - self.sessions[user_id]['last_activity'] > SESSION_EXPIRY:
            self.sessions[user_id] = {
                'messages': [{"role": "developer", "content": SYSTEM_PROMPT}],
                'last_activity': current_time,
                'model_provider': DEFAULT_MODEL_PROVIDER,
                'model': OPENAI_MODEL if DEFAULT_MODEL_PROVIDER == 'openai' else ANTHROPIC_MODEL if DEFAULT_MODEL_PROVIDER == 'anthropic' else GEMINI_MODEL if DEFAULT_MODEL_PROVIDER == 'gemini' else GROK_MODEL,
                'image_model': 'openai',  # Default image model
                'state': None
            }
        else:
            self.sessions[user_id]['last_activity'] = current_time

        return Session(self.sessions[user_id])

    def create_new_session(self, user_id: int) -> None:
        # Preserve model preferences when creating a new session
        model_provider = self.sessions.get(user_id, {}).get('model_provider', DEFAULT_MODEL_PROVIDER)
        model = self.sessions.get(user_id, {}).get('model',
                                                  OPENAI_MODEL if model_provider == 'openai' else ANTHROPIC_MODEL if model_provider == 'anthropic' else GEMINI_MODEL if model_provider == 'gemini' else GROK_MODEL)
        image_model = self.sessions.get(user_id, {}).get('image_model', 'openai')

        self.sessions[user_id] = {
            'messages': [{"role": "developer", "content": SYSTEM_PROMPT}],
            'last_activity': time.time(),
            'model_provider': model_provider,
            'model': model,
            'image_model': image_model,
            'state': None
        }

    def get_model_provider(self, user_id: int) -> str:
        """Get the current model provider for a user session"""
        if user_id not in self.sessions:
            return DEFAULT_MODEL_PROVIDER
        return self.sessions[user_id].get('model_provider', DEFAULT_MODEL_PROVIDER)

    def set_model_provider(self, user_id: int, provider: str) -> None:
        """Set the model provider for a user session"""
        if user_id in self.sessions:
            self.sessions[user_id]['model_provider'] = provider
            if provider == 'openai':
                self.sessions[user_id]['model'] = OPENAI_MODEL
            elif provider == 'anthropic':
                self.sessions[user_id]['model'] = ANTHROPIC_MODEL
            elif provider == 'gemini':
                self.sessions[user_id]['model'] = GEMINI_MODEL
            else:
                self.sessions[user_id]['model'] = GROK_MODEL
        else:
            self.sessions[user_id] = {
                'messages': [{"role": "developer", "content": SYSTEM_PROMPT}],
                'last_activity': time.time(),
                'model_provider': provider,
                'model': OPENAI_MODEL if provider == 'openai' else ANTHROPIC_MODEL if provider == 'anthropic' else GEMINI_MODEL if provider == 'gemini' else GROK_MODEL,
                'image_model': 'openai',
                'state': None
            }

    def get_model(self, user_id: int) -> dict:
        """Get the current provider model for a user session"""
        if user_id not in self.sessions:
            return DEFAULT_MODEL

        provider = self.sessions[user_id].get('model_provider', DEFAULT_MODEL_PROVIDER)

        # Find the model in MODELS list by provider
        for model in MODELS:
            if model['provider'] == provider:
                return model

        # If model not found, return default
        return DEFAULT_MODEL

class Session:
    def __init__(self, session_data):
        self.data = session_data

    def update_state(self, state: str) -> None:
        """Update the state of the session"""
        logger.info(f"Updating session state to: {state}")
        self.data['state'] = state

    def get_state(self) -> Optional[str]:
        """Get the current state of the session"""
        state = self.data.get('state')
        logger.info(f"Getting session state: {state}")
        return state

    def clear_state(self) -> None:
        """Clear the state of the session"""
        logger.info(f"Clearing session state from: {self.data.get('state')}")
        self.data['state'] = None

    def update_model(self, provider_id: str) -> None:
        """Update the provider for this session"""
        logger.info(f"Updating model provider to: {provider_id}")
        self.data['model_provider'] = provider_id
        # Set default model for the provider
        if provider_id == 'openai':
            self.data['model'] = OPENAI_MODEL
        elif provider_id == 'anthropic':
            self.data['model'] = ANTHROPIC_MODEL
        elif provider_id == 'gemini':
            self.data['model'] = GEMINI_MODEL
        else:
            self.data['model'] = GROK_MODEL

    def update_specific_model(self, model_id: str) -> None:
        """Update the specific model for this session"""
        logger.info(f"Updating specific model to: {model_id}")
        self.data['model'] = model_id

    def get_provider(self) -> str:
        """Get the provider for the current model"""
        provider = self.data.get('model_provider', DEFAULT_MODEL_PROVIDER)
        logger.info(f"Current provider is: {provider}")
        return provider

    def get_model(self) -> str:
        """Get the current specific model"""
        provider = self.get_provider()
        if provider == 'openai':
            default_model = OPENAI_MODEL
        elif provider == 'anthropic':
            default_model = ANTHROPIC_MODEL
        elif provider == 'gemini':
            default_model = GEMINI_MODEL
        else:
            default_model = GROK_MODEL
        return self.data.get('model', default_model)

    def update_image_model(self, model_id: str) -> None:
        """Update the image generation model for this session"""
        self.data['image_model'] = model_id

    def get_image_model(self) -> str:
        """Get the current image generation model"""
        return self.data.get('image_model', 'openai')

    async def process_openai_message(self, message: str, openai_client):
        """Process a message using OpenAI"""
        messages = self.data.get('messages', [])

        # Add user message
        messages.append({"role": "user", "content": message})

        # Use model from session or client config
        model_id = self.get_model()

        # Extract system/developer messages as instructions (Responses API)
        instructions_parts = []
        input_items = []
        for m in messages:
            if m["role"] == "developer":
                instructions_parts.append(m["content"])
            elif m["role"] in ("user", "assistant"):
                input_items.append({"role": m["role"], "content": m["content"]})

        instructions = "\n".join(instructions_parts) if instructions_parts else None

        try:
            kwargs = {"model": model_id, "input": input_items}
            if instructions:
                kwargs["instructions"] = instructions

            async with openai_client.get_client() as client:
                response = await client.responses.create(**kwargs)

            assistant_message = response.output_text

            messages.append({"role": "assistant", "content": assistant_message})
            self.data['messages'] = messages

            return assistant_message

        except Exception as e:
            return f"Error processing message with OpenAI: {str(e)}"

    async def process_claude_message(self, message: str, claude_client):
        """Process a message using Claude"""
        messages = self.data.get('messages', [])

        # Add user message
        messages.append({"role": "user", "content": message})

        # Use model from session or client config
        model_id = self.get_model()

        try:
            # Convert messages to Claude format
            claude_messages = []
            for m in messages:
                role = "user" if m["role"] == "user" else "assistant"
                if m["role"] == "developer":
                    # Handle system message
                    continue  # Claude has a different way of handling system messages
                claude_messages.append({"role": role, "content": m["content"]})

            # Call Claude API
            async with claude_client.get_client() as client:
                response = await client.messages.create(
                    model=model_id,
                    max_tokens=4096,
                    messages=claude_messages,
                    system=SYSTEM_PROMPT
                )

            # Get assistant's response
            assistant_message = response.content[0].text

            # Add assistant message to history
            messages.append({"role": "assistant", "content": assistant_message})

            # Update messages in session data
            self.data['messages'] = messages

            return assistant_message

        except Exception as e:
            return f"Error processing message with Claude: {str(e)}"

    async def process_gemini_message(self, message: str, gemini_client):
        """Process a message using Google Gemini"""
        messages = self.data.get('messages', [])

        messages.append({"role": "user", "content": message})

        model_id = self.get_model()

        try:
            async with gemini_client.get_client() as client:
                def _call():
                    model = client.GenerativeModel(model_id)
                    resp = model.generate_content([
                        {"role": "user", "parts": [m["content"]]} if m["role"] == "user" else {"role": "model", "parts": [m["content"]]} for m in messages if m["role"] != "developer"
                    ])
                    return resp.text

                assistant_message = await asyncio.to_thread(_call)

            messages.append({"role": "assistant", "content": assistant_message})
            self.data['messages'] = messages
            return assistant_message
        except Exception as e:
            return f"Error processing message with Gemini: {str(e)}"

    async def process_gemini_message_with_image(self, message: str, image_urls: List[str], gemini_client):
        messages = self.data.get('messages', [])
        for url in image_urls:
            if not url.startswith(('http://', 'https://')):
                url = f"https://api.telegram.org/file/bot{gemini_client.telegram_bot_token}/{url}"
            messages.append({"role": "user", "content": {"type": "image", "source": url}})

        messages.append({"role": "user", "content": message})

        model_id = self.get_model()
        try:
            async with gemini_client.get_client() as client:
                def _call():
                    model = client.GenerativeModel(model_id)
                    resp = model.generate_content([
                        {"role": "user", "parts": [m["content"]]} if m["role"] == "user" else {"role": "model", "parts": [m["content"]]} for m in messages if m["role"] != "developer"
                    ])
                    return resp.text
                assistant_message = await asyncio.to_thread(_call)

            self.data['messages'] = [msg for msg in messages if isinstance(msg['content'], str)] + [{"role": "assistant", "content": assistant_message}]
            return assistant_message
        except Exception as e:
            return f"Error processing message with Gemini: {str(e)}"

    async def process_grok_message(self, message: str, grok_client):
        """Process a message using Grok (OpenAI-compatible)"""
        messages = self.data.get('messages', [])

        messages.append({"role": "user", "content": message})

        model_id = self.get_model()

        try:
            async with grok_client.get_client() as client:
                response = await client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": m["role"], "content": m["content"]} for m in messages]
                )
            assistant_message = response.choices[0].message.content

            messages.append({"role": "assistant", "content": assistant_message})
            self.data['messages'] = messages
            return assistant_message
        except Exception as e:
            return f"Error processing message with Grok: {str(e)}"

    async def process_grok_message_with_image(self, message: str, image_urls: List[str], grok_client):
        message_content = [{"type": "text", "text": message}]
        for url in image_urls:
            if not url.startswith(('http://', 'https://')):
                url = f"https://api.telegram.org/file/bot{grok_client.telegram_bot_token}/{url}"
            message_content.append({
                "type": "image_url",
                "image_url": {"url": url, "detail": "auto"}
            })

        model_to_use = self.get_model()
        messages = self.data.get('messages', [])
        history_messages = []
        for m in messages:
            if m["role"] in ("user", "assistant", "developer"):
                role = "system" if m["role"] == "developer" else m["role"]
                history_messages.append({"role": role, "content": m["content"]})
        history_messages.append({"role": "user", "content": message_content})

        try:
            async with grok_client.get_client() as client:
                response = await client.chat.completions.create(
                    model=model_to_use,
                    messages=history_messages
                )
            reply = response.choices[0].message.content.strip()

            messages.append({"role": "user", "content": message + " [with images]"})
            messages.append({"role": "assistant", "content": reply})
            self.data['messages'] = messages
            return reply
        except Exception as e:
            return f"Error processing message with Grok: {str(e)}"
