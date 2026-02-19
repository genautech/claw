"""
Keys Manager - Manage API keys securely
"""

import json
import os
from pathlib import Path
import streamlit as st

OPENCLAW_DIR = Path.home() / ".openclaw"
CONFIG_FILE = OPENCLAW_DIR / "openclaw.json"

st.title("🔑 Keys Manager")
st.markdown("Manage API keys for ClawdBot services")

# Load config
config = {}
if CONFIG_FILE.exists():
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    except Exception as e:
        st.warning(f"Could not load config: {e}")

# API Keys to manage
keys_section = st.container()

with keys_section:
    st.subheader("API Keys")
    
    # OpenRouter API Key
    st.markdown("#### OpenRouter API Key")
    st.caption("For LLM access (DeepSeek, Grok, etc.)")
    openrouter_key = st.text_input(
        "OpenRouter API Key",
        value=os.getenv("OPENROUTER_API_KEY", ""),
        type="password",
        key="openrouter_key"
    )
    if st.button("Save OpenRouter Key", key="save_openrouter"):
        # Store in environment or config
        st.info("💡 Store this in your .env file or config file")
        st.code(f"export OPENROUTER_API_KEY={openrouter_key}")
    
    st.divider()
    
    # Chainstack Node URL
    st.markdown("#### Chainstack Polygon Node")
    st.caption("RPC endpoint for Polygon network")
    chainstack_node = st.text_input(
        "Chainstack Node URL",
        value=os.getenv("CHAINSTACK_NODE", ""),
        type="default",
        key="chainstack_node"
    )
    if st.button("Save Chainstack Node", key="save_chainstack"):
        st.info("💡 Store this in your .env file or config file")
        st.code(f"export CHAINSTACK_NODE={chainstack_node}")
    
    st.divider()
    
    # Polyclaw Operator API Key
    st.markdown("#### Polyclaw Operator API Key")
    st.caption("From polyclaw.ai dashboard (pc_op_...)")
    polyclaw_op_key = st.text_input(
        "Polyclaw Operator Key",
        value=os.getenv("POLYCLAW_OPERATOR_API_KEY", ""),
        type="password",
        key="polyclaw_op_key"
    )
    if st.button("Save Polyclaw Operator Key", key="save_polyclaw_op"):
        st.info("💡 Store this in your .env file")
        st.code(f"export POLYCLAW_OPERATOR_API_KEY={polyclaw_op_key}")
    
    st.divider()
    
    # Polyclaw Agent API Key
    st.markdown("#### Polyclaw Agent API Key")
    st.caption("Agent-specific key (pc_agent_...)")
    polyclaw_agent_key = st.text_input(
        "Polyclaw Agent Key",
        value=os.getenv("POLYCLAW_AGENT_API_KEY", ""),
        type="password",
        key="polyclaw_agent_key"
    )
    if st.button("Save Polyclaw Agent Key", key="save_polyclaw_agent"):
        st.info("💡 Store this in your .env file")
        st.code(f"export POLYCLAW_AGENT_API_KEY={polyclaw_agent_key}")
    
    st.divider()
    
    # Telegram Bot Token
    st.markdown("#### Telegram Bot Token")
    st.caption("From @BotFather")
    telegram_token = st.text_input(
        "Telegram Bot Token",
        value=config.get("channels", {}).get("telegram", {}).get("botToken", ""),
        type="password",
        key="telegram_token"
    )
    if st.button("Save Telegram Token", key="save_telegram"):
        if "channels" not in config:
            config["channels"] = {}
        if "telegram" not in config["channels"]:
            config["channels"]["telegram"] = {}
        config["channels"]["telegram"]["botToken"] = telegram_token
        
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            st.success("Telegram token saved to config!")
        except Exception as e:
            st.error(f"Error saving: {e}")
    
    st.divider()
    
    # Firebase API Key (for Cloud Run API)
    st.markdown("#### Firebase/Cloud Run API Key")
    st.caption("For accessing the Cloud Run backend API")
    firebase_api_key = st.text_input(
        "Firebase API Key",
        value=os.getenv("FIREBASE_API_KEY", ""),
        type="password",
        key="firebase_api_key"
    )
    if st.button("Save Firebase API Key", key="save_firebase"):
        st.info("💡 Store this in your .env file")
        st.code(f"export FIREBASE_API_KEY={firebase_api_key}")

# Validation section
st.divider()
st.subheader("Key Validation")

col1, col2 = st.columns(2)

with col1:
    if st.button("Validate All Keys"):
        results = []
        
        # Check OpenRouter
        if openrouter_key:
            results.append(("OpenRouter", "✅ Set", "green"))
        else:
            results.append(("OpenRouter", "❌ Missing", "red"))
        
        # Check Chainstack
        if chainstack_node and "chainstack.com" in chainstack_node:
            results.append(("Chainstack", "✅ Valid", "green"))
        elif chainstack_node:
            results.append(("Chainstack", "⚠️ Check URL", "orange"))
        else:
            results.append(("Chainstack", "❌ Missing", "red"))
        
        # Check Telegram
        if telegram_token and len(telegram_token) > 20:
            results.append(("Telegram", "✅ Set", "green"))
        else:
            results.append(("Telegram", "❌ Missing", "red"))
        
        for name, status, color in results:
            if color == "green":
                st.success(f"{name}: {status}")
            elif color == "orange":
                st.warning(f"{name}: {status}")
            else:
                st.error(f"{name}: {status}")

with col2:
    st.markdown("**Security Tips:**")
    st.markdown("- Never commit keys to git")
    st.markdown("- Use .env file for local dev")
    st.markdown("- Rotate keys regularly")
    st.markdown("- Use separate keys per environment")
