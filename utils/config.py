import os


def get_secret(key: str, default: str = None) -> str:
    """
    Read a config value from the first source that has it:
      1. os.environ  (local .env via load_dotenv, or system env)
      2. st.secrets  (Streamlit Cloud dashboard secrets)
      3. default
    """
    val = os.environ.get(key)
    if val:
        return val
    try:
        import streamlit as st
        val = st.secrets.get(key)
        if val:
            return val
    except Exception:
        pass
    return default
