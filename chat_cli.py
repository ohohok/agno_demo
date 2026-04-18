"""
Interactive chat mode for Agno Agent with Zhipu AI (GLM)
Run this file to start a conversation with the agent in your terminal
"""
import os
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.openai import OpenAIChat

# Load environment variables from .env file
load_dotenv()


def create_chat_agent():
    """Create an agent configured for chat with Zhipu AI"""
    # Get API key from environment variable or prompt user
    api_key = os.getenv("ZHIPUAI_API_KEY")
    if not api_key:
        print("⚠️  Warning: ZHIPUAI_API_KEY environment variable not set!")
        print("   Please set it before running: export ZHIPUAI_API_KEY='your-api-key'")
        print("   Or get your API key from: https://open.bigmodel.cn/")
        api_key = input("\n🔑 Enter your Zhipu AI API key: ").strip()

    return Agent(
        model=OpenAIChat(
            id="glm-4-flash",
            base_url="https://open.bigmodel.cn/api/paas/v4/",
            api_key=api_key,
            temperature=0.7,
            max_tokens=2048,
        )
    )


def interactive_chat():
    """Start an interactive chat session"""
    print("=" * 60)
    print("🤖 Agno AI Assistant - Interactive Chat Mode")
    print("=" * 60)
    print("\n💡 Tips:")
    print("   - Type your message and press Enter to chat")
    print("   - Type 'exit', 'quit', or 'q' to end the conversation")
    print("   - Type 'clear' to clear conversation history")
    print("   - Using Zhipu AI GLM model (glm-4-flash)")
    print("   - Make sure to set ZHIPUAI_API_KEY environment variable")
    print("\n" + "=" * 60)

    # Create the agent
    agent = create_chat_agent()

    # Start chat loop
    while True:
        try:
            # Get user input
            user_input = input("\n👤 You: ").strip()

            # Check for exit commands
            if user_input.lower() in ['exit', 'quit', 'q']:
                print("\n👋 Goodbye! Have a great day!")
                break

            # Check for clear command
            if user_input.lower() == 'clear':
                agent.session_state = {}
                print("\n🗑️ Conversation history cleared!")
                continue

            # Skip empty input
            if not user_input:
                continue

            # Get response from agent
            print("\n🤖 Agent is thinking...")
            response = agent.run(user_input)

            # Print response
            if response and response.content:
                print(f"\n🤖 Agent:\n{response.content}")
            else:
                print("\n⚠️ Sorry, I couldn't generate a response.")
                if response:
                    print(f"DEBUG: Response object: {response}")
                    if hasattr(response, 'tools') and response.tools:
                        print(f"DEBUG: Agent called tools: {response.tools}")

        except KeyboardInterrupt:
            print("\n\n👋 Interrupted! Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            print("Please try again.")


if __name__ == "__main__":
    interactive_chat()
