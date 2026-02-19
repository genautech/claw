"""
Config Editor - Edit OpenClaw configuration
"""

import json
from pathlib import Path
import streamlit as st

OPENCLAW_DIR = Path.home() / ".openclaw"
CONFIG_FILE = OPENCLAW_DIR / "openclaw.json"

st.title("⚙️ Config Editor")
st.markdown("Edit OpenClaw gateway configuration")

if not CONFIG_FILE.exists():
    st.error(f"Config file not found at {CONFIG_FILE}")
    st.info("Run `openclaw onboard` first to create the config file.")
    st.stop()

# Load current config
try:
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
except Exception as e:
    st.error(f"Error reading config: {e}")
    st.stop()

# Display current config as editable JSON
st.subheader("Current Configuration")

# Split into sections for easier editing
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Gateway", "Channels", "Skills", "Tools", "Raw JSON"])

with tab1:
    st.markdown("### Gateway Settings")
    gateway_mode = st.selectbox("Mode", ["local", "cloud"], index=0 if config.get("gateway", {}).get("mode") == "local" else 1)
    gateway_port = st.number_input("Port", min_value=1024, max_value=65535, value=config.get("gateway", {}).get("port", 18789))
    gateway_bind = st.selectbox("Bind", ["loopback", "all"], index=0 if config.get("gateway", {}).get("bind") == "loopback" else 1)
    
    st.markdown("#### Auth")
    auth_mode = st.selectbox("Auth Mode", ["token", "none"], index=0 if config.get("gateway", {}).get("auth", {}).get("mode") == "token" else 1)
    auth_token = st.text_input("Token", value=config.get("gateway", {}).get("auth", {}).get("token", ""), type="password")
    
    if st.button("Update Gateway", key="gateway_update"):
        if "gateway" not in config:
            config["gateway"] = {}
        config["gateway"]["mode"] = gateway_mode
        config["gateway"]["port"] = gateway_port
        config["gateway"]["bind"] = gateway_bind
        config["gateway"]["auth"] = {"mode": auth_mode, "token": auth_token}
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        st.success("Gateway config updated!")

with tab2:
    st.markdown("### Channel Settings")
    
    if "channels" not in config:
        config["channels"] = {}
    
    # Telegram
    st.markdown("#### Telegram")
    telegram_enabled = st.checkbox("Enable Telegram", value="telegram" in config.get("channels", {}))
    if telegram_enabled:
        telegram_bot_token = st.text_input("Bot Token", value=config.get("channels", {}).get("telegram", {}).get("botToken", ""), type="password")
        telegram_dm_policy = st.selectbox("DM Policy", ["pairing", "open"], index=0 if config.get("channels", {}).get("telegram", {}).get("dmPolicy") == "pairing" else 1)
        telegram_group_policy = st.selectbox("Group Policy", ["allowlist", "open"], index=0 if config.get("channels", {}).get("telegram", {}).get("groupPolicy") == "allowlist" else 1)
        
        if st.button("Update Telegram", key="telegram_update"):
            if "telegram" not in config["channels"]:
                config["channels"]["telegram"] = {}
            config["channels"]["telegram"]["botToken"] = telegram_bot_token
            config["channels"]["telegram"]["dmPolicy"] = telegram_dm_policy
            config["channels"]["telegram"]["groupPolicy"] = telegram_group_policy
            config["channels"]["telegram"]["streamMode"] = "partial"
            config["channels"]["telegram"]["groups"] = {
                "/openslaver": {"requireMention": False},
                "*": {"requireMention": True}
            }
            
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            st.success("Telegram config updated!")
    
    # Discord
    st.markdown("#### Discord")
    discord_enabled = st.checkbox("Enable Discord", value="discord" in config.get("channels", {}))
    if discord_enabled:
        discord_dm_policy = st.selectbox("DM Policy", ["pairing", "open"], index=0 if config.get("channels", {}).get("discord", {}).get("dmPolicy") == "pairing" else 1, key="discord_dm")
        if st.button("Update Discord", key="discord_update"):
            if "discord" not in config["channels"]:
                config["channels"]["discord"] = {}
            config["channels"]["discord"]["dmPolicy"] = discord_dm_policy
            config["channels"]["discord"]["groupPolicy"] = "allowlist"
            
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            st.success("Discord config updated!")

with tab3:
    st.markdown("### Skills Configuration")
    
    if "skills" not in config:
        config["skills"] = {"entries": {}}
    
    skills = config.get("skills", {}).get("entries", {})
    
    st.markdown("#### Installed Skills")
    for skill_name, skill_config in skills.items():
        with st.expander(f"📦 {skill_name}"):
            enabled = st.checkbox("Enabled", value=skill_config.get("enabled", False), key=f"skill_{skill_name}_enabled")
            
            if "env" in skill_config:
                st.markdown("**Environment Variables:**")
                for env_key, env_value in skill_config["env"].items():
                    new_value = st.text_input(env_key, value=env_value, type="password" if "key" in env_key.lower() or "token" in env_key.lower() else "default", key=f"skill_{skill_name}_{env_key}")
                    skill_config["env"][env_key] = new_value
            
            if st.button(f"Update {skill_name}", key=f"skill_{skill_name}_update"):
                skill_config["enabled"] = enabled
                config["skills"]["entries"][skill_name] = skill_config
                
                with open(CONFIG_FILE, 'w') as f:
                    json.dump(config, f, indent=2)
                st.success(f"{skill_name} updated!")

with tab4:
    st.markdown("### Tools & Security")
    
    if "tools" not in config:
        config["tools"] = {}
    
    tools_profile = st.selectbox("Profile", ["messaging", "full"], index=0 if config.get("tools", {}).get("profile") == "messaging" else 1)
    tools_fs_workspace_only = st.checkbox("Filesystem: Workspace Only", value=config.get("tools", {}).get("fs", {}).get("workspaceOnly", True))
    tools_exec_security = st.selectbox("Exec Security", ["deny", "allow"], index=0 if config.get("tools", {}).get("exec", {}).get("security") == "deny" else 1)
    tools_elevated_enabled = st.checkbox("Elevated Tools Enabled", value=config.get("tools", {}).get("elevated", {}).get("enabled", False))
    
    if st.button("Update Tools", key="tools_update"):
        config["tools"]["profile"] = tools_profile
        config["tools"]["fs"] = {"workspaceOnly": tools_fs_workspace_only}
        config["tools"]["exec"] = {"security": tools_exec_security, "ask": "always"}
        config["tools"]["elevated"] = {"enabled": tools_elevated_enabled}
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        st.success("Tools config updated!")

with tab5:
    st.markdown("### Raw JSON Editor")
    st.warning("⚠️ Edit with caution! Invalid JSON will break the config.")
    
    edited_config = st.text_area("Config JSON", value=json.dumps(config, indent=2), height=600)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Validate JSON"):
            try:
                json.loads(edited_config)
                st.success("✅ Valid JSON")
            except json.JSONDecodeError as e:
                st.error(f"❌ Invalid JSON: {e}")
    
    with col2:
        if st.button("Save Config"):
            try:
                parsed = json.loads(edited_config)
                with open(CONFIG_FILE, 'w') as f:
                    json.dump(parsed, f, indent=2)
                st.success("Config saved!")
                st.rerun()
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")
            except Exception as e:
                st.error(f"Error saving: {e}")
