from contextlib import asynccontextmanager
from typing import List, Dict, Any

from openai import AsyncOpenAI, OpenAIError, RateLimitError

from utils.logging_config import logger
from config import OPENAI_API_KEY, TELEGRAM_BOT_TOKEN, OPENAI_REASONING_EFFORT


class OpenAIClient:
    def __init__(self):
        self.api_key = OPENAI_API_KEY
        self.telegram_bot_token = TELEGRAM_BOT_TOKEN

    @asynccontextmanager
    async def get_client(self):
        async with AsyncOpenAI(api_key=self.api_key) as client:
            yield client

    async def process_message(self, session: Any, user_message: str) -> str:
        try:
            logger.info("Sending request to OpenAI Responses API")

            response = await session.process_openai_message(user_message, self)

            logger.info(f"Received response from OpenAI API: {response}")
            return response
        except RateLimitError as e:
            logger.error(f"Rate limit exceeded: {e}")
            return "API rate limit reached. Please try again later."
        except OpenAIError as e:
            logger.error(f"OpenAI API Error: {e}")
            return "Sorry, there was a problem with OpenAI. Please try again."
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return "An unexpected error occurred."

    async def process_message_with_image(
        self, session: Any, user_message: str, image_urls: List[str]
    ) -> str:
        """Send a message with images to OpenAI using the Responses API."""

        message_content: List[Dict[str, str]] = [
            {"type": "input_text", "text": user_message}
        ]

        for url in image_urls:
            if not url.startswith(("http://", "https://")):
                full_url = f"https://api.telegram.org/file/bot{self.telegram_bot_token}/{url}"
                logger.debug(
                    f"Converting relative path to full URL: {url} -> {full_url}"
                )
                url = full_url
            message_content.append({"type": "input_image", "image_url": url})

        model_to_use = session.get_model()
        # Responses API supports reasoning models; keep model as-is

        try:
            logger.info(
                f"Sending request to OpenAI Responses API with {len(image_urls)} images using model {model_to_use}"
            )
            logger.debug(
                f"Final image URLs: {[item['image_url'] for item in message_content if item['type'] == 'input_image']}"
            )

            messages = session.data.get("messages", [])
            instructions_parts = []
            history_messages = []
            for m in messages:
                if m["role"] == "developer":
                    instructions_parts.append(m["content"])
                elif m["role"] in ("user", "assistant"):
                    history_messages.append({"role": m["role"], "content": m["content"]})

            history_messages.append({
                "role": "user",
                "content": [
                    {"type": "input_text", "text": user_message},
                    *[
                        {"type": "input_image", "image_url": item["image_url"]}
                        for item in message_content
                        if isinstance(item, dict) and item.get("type") == "input_image"
                    ]
                ]
            })

            kwargs = {"model": model_to_use, "input": history_messages}
            instructions = "\n".join(instructions_parts) if instructions_parts else None
            if instructions:
                kwargs["instructions"] = instructions
            if OPENAI_REASONING_EFFORT:
                kwargs["reasoning"] = {"effort": OPENAI_REASONING_EFFORT}

            async with self.get_client() as client:
                response = await client.responses.create(**kwargs)
            reply = response.output_text.strip()

            messages.append({"role": "user", "content": user_message + " [with images]"})
            messages.append({"role": "assistant", "content": reply})
            session.data["messages"] = messages

            logger.info(f"Received response from OpenAI API: {reply}")
            return reply
        except RateLimitError as e:
            logger.error(f"Rate limit exceeded: {e}")
            return "API rate limit reached. Please try again later."
        except OpenAIError as e:
            logger.error(f"OpenAI API Error: {e}")
            return "Sorry, there was a problem with OpenAI. Please try again."
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return "An unexpected error occurred."

    async def generate_image(self, prompt: str):
        """Generate an image using OpenAI's DALL-E model.

        Args:
            prompt (str): The text prompt for image generation

        Returns:
            bytes: The generated image as bytes
        """
        logger.info(f"Generating image with OpenAI: {prompt}")
        try:
            async with self.get_client() as client:
                response = await client.images.generate(
                    model="gpt-image-1",
                    prompt=prompt,
                    size="1024x1024",
                    quality="medium",
                    n=1,
                )
            import base64

            return base64.b64decode(response.data[0].b64_json)
        except Exception as e:
            logger.error(f"Error generating image with OpenAI: {e}")
            raise

